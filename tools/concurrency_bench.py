#!/usr/bin/env python3
"""Measure established proxy connections and same-socket survival, without reconfiguration."""
import argparse
import concurrent.futures
import datetime
import http.client
import json
from pathlib import Path
import queue
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fraction(count, total):
    return round(count / total, 4) if total else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-config', required=True)
    parser.add_argument('--proxy', default='http://127.0.0.1:18891')
    parser.add_argument('--controller', default='http://127.0.0.1:18892')
    parser.add_argument('--levels', nargs='+', type=int, default=[16, 32, 64])
    parser.add_argument('--waves', type=int, default=3)
    parser.add_argument('--hold-seconds', type=int, default=15)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.levels != sorted(set(args.levels)) or not all(1 <= n <= 256 for n in args.levels):
        parser.error('levels must increase without duplicates, from 1 through 256')
    if not 1 <= args.waves <= 5 or not 1 <= args.hold_seconds <= 30:
        parser.error('waves must be 1..5; hold-seconds must be 1..30')
    proxy = urllib.parse.urlsplit(args.proxy)
    if proxy.scheme != 'http' or proxy.hostname not in ('localhost', '127.0.0.1', '::1'):
        parser.error('use an isolated HTTP proxy on loopback')
    if args.controller:
        controller = urllib.parse.urlsplit(args.controller)
        if controller.scheme != 'http' or controller.hostname not in ('localhost', '127.0.0.1', '::1'):
            parser.error('controller must be an HTTP endpoint on loopback')
    private = json.loads(Path(args.private_config).read_text())
    url = urllib.parse.urlsplit(private['subscription'])
    if url.scheme != 'https':
        parser.error('subscription must use HTTPS')
    node = private['profile']['proxies'][0]
    if url.hostname != node['server']:
        parser.error('subscription and node must refer to the same VPS')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'summary.json').exists() or (out / 'connections.jsonl').exists():
        parser.error('use a fresh output directory')
    context = ssl.create_default_context()
    path = urllib.parse.urlunsplit(('', '', url.path, url.query, ''))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def clean(error):
        text = str(error)
        for value in (private['subscription'], path, node['uuid'], node['server']):
            text = text.replace(value, '<redacted>')
        return re.sub(r'(?:\d{1,3}\.){3}\d{1,3}', '<IP>', text)

    def controller_count():
        if not args.controller:
            return None
        try:
            headers = {'Authorization': 'Bearer ' + private.get('controller_secret', '')}
            request = urllib.request.Request(args.controller.rstrip('/') + '/connections', headers=headers)
            with opener.open(request, timeout=2) as response:
                return len(json.load(response).get('connections') or [])
        except Exception:
            return None

    waves, rows, stopped = [], [], False
    started = stamp()
    for level in args.levels:
        for wave in range(1, args.waves + 1):
            start_gate = threading.Barrier(level + 1)
            release = threading.Event()
            opened = queue.Queue()

            def worker(index):
                row = dict(level=level, wave=wave, index=index, setup_ok=False,
                           reuse_ok=False, same_socket=False, error='')
                connection = http.client.HTTPSConnection(
                    proxy.hostname, proxy.port or 80, timeout=10, context=context)
                connection.set_tunnel(url.hostname, url.port or 443)
                start_gate.wait(timeout=20)
                begin = time.monotonic()
                row['started_utc'] = stamp()
                try:
                    connection.connect()
                    # Forbid http.client from silently reopening a closed socket.
                    connection.auto_open = 0
                    original_socket = connection.sock

                    def get():
                        connection.request('GET', path, headers={'Connection': 'keep-alive'})
                        response = connection.getresponse()
                        if response.length is None or response.length > 65536:
                            raise ValueError('response requires a known length <=64 KiB')
                        body = response.read()
                        if response.status != 200 or json.loads(body)['proxies'][0]['uuid'] != node['uuid']:
                            raise ValueError('subscription response validation failed')
                        if response.will_close or connection.sock is not original_socket:
                            raise ValueError('server did not preserve the original keep-alive socket')

                    get()
                    row['setup_s'] = round(time.monotonic() - begin, 6)
                    row['setup_ok'] = True
                except Exception as error:
                    row['setup_s'] = round(time.monotonic() - begin, 6)
                    row['error'] = clean(error)
                    opened.put(False)
                    connection.close()
                    return row
                opened.put(True)
                try:
                    if not release.wait(timeout=args.hold_seconds + 60):
                        raise TimeoutError('benchmark release event timed out')
                    begin = time.monotonic()
                    get()
                    row['reuse_s'] = round(time.monotonic() - begin, 6)
                    row['same_socket'] = connection.sock is original_socket
                    row['reuse_ok'] = row['same_socket']
                except Exception as error:
                    row['error'] = clean(error)
                finally:
                    connection.close()
                return row

            with concurrent.futures.ThreadPoolExecutor(max_workers=level) as pool:
                futures = [pool.submit(worker, i) for i in range(level)]
                gate_time = stamp()
                start_gate.wait(timeout=20)
                states = []
                try:
                    for _ in range(level):
                        states.append(opened.get(timeout=40))
                    counts = []
                    hold_start = stamp()
                    hold_begin = time.monotonic()
                    deadline = hold_begin + args.hold_seconds
                    while time.monotonic() < deadline:
                        count = controller_count()
                        if count is not None:
                            counts.append(count)
                        time.sleep(min(1, max(0, deadline-time.monotonic())))
                    hold_elapsed = time.monotonic() - hold_begin
                finally:
                    release.set()
                measured = [f.result() for f in futures]
            rows.extend(measured)
            with (out / 'connections.jsonl').open('a') as stream:
                for row in measured:
                    stream.write(json.dumps(row) + '\n')
            successes = sum(r['setup_ok'] for r in measured)
            reused = sum(r['reuse_ok'] for r in measured)
            summary = dict(level=level, wave=wave, start_utc=gate_time,
                           hold_start_utc=hold_start, hold_seconds_minimum=args.hold_seconds,
                           hold_elapsed_s=round(hold_elapsed, 4),
                           attempted=level, established=successes, same_socket_reused=reused,
                           establish_rate=fraction(successes, level),
                           reuse_rate_of_established=fraction(reused, successes),
                           controller_connection_samples=counts,
                           controller_peak=max(counts) if counts else None,
                           controller_min=min(counts) if counts else None)
            waves.append(summary)
            print(json.dumps(summary), flush=True)
            (out / 'summary.json').write_text(json.dumps(dict(
                started_utc=started, updated_utc=stamp(), waves=waves,
                hidden_reconnects=False, stopped_early=stopped), indent=2) + '\n')
            if successes / level < .95 or (successes and reused / successes < .95):
                stopped = True
                print('FAILURE GATE: no higher concurrency will be attempted', flush=True)
                break
            time.sleep(3)
        if stopped:
            break
    (out / 'summary.json').write_text(json.dumps(dict(
        started_utc=started, ended_utc=stamp(), waves=waves,
        hidden_reconnects=False, stopped_early=stopped), indent=2) + '\n')


if __name__ == '__main__':
    main()
