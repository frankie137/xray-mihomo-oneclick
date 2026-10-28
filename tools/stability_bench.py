#!/usr/bin/env python3
"""Bounded connectivity benchmark for an existing proxy. Never changes services."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    rank = (len(values) - 1) * p
    lo = int(rank)
    hi = min(lo + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (rank - lo), 4)


def summarize(rows):
    good = [r for r in rows if r['ok']]
    times = [r['total_s'] for r in good]
    return dict(requests=len(rows), success=len(good), failed=len(rows)-len(good),
                success_rate=round(len(good)/len(rows), 4) if rows else None,
                latency_success_only_s=dict(p50=percentile(times, .5),
                p95=percentile(times, .95), p99=percentile(times, .99),
                max=round(max(times), 4) if times else None),
                failure_total_s=[r['total_s'] for r in rows if not r['ok']])


def redact(text, values):
    for value in sorted((x for x in values if x), key=len, reverse=True):
        text = text.replace(value, "<redacted>")
    return re.sub(r"(?:\d{1,3}\.){3}\d{1,3}", "<IP>", text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-config', required=True,
                   help='JSON with subscription URL and matching profile; never published')
    p.add_argument('--proxy', default='http://127.0.0.1:18891')
    p.add_argument('--interface', default='en0', help='Interface for outside-proxy controls')
    p.add_argument('--output', required=True)
    p.add_argument('--mode', choices=['ramped', 'bursts', 'idle'], default='ramped')
    p.add_argument('--rps', type=float, default=2.0)
    p.add_argument('--timeout', type=int, default=10)
    p.add_argument('--idle-seconds', type=int, default=60)
    a = p.parse_args()
    if not 0 < a.rps <= 4 or not 1 <= a.timeout <= 15 or not 0 <= a.idle_seconds <= 60:
        p.error('Limits: 0 < rps <= 4; timeout 1..15; idle-seconds 0..60')
    private = json.loads(Path(a.private_config).read_text())
    node = private['profile']['proxies'][0]
    ip = node['server']
    targets = {'self_http': ('http://'+ip+'/', 404),
               'subscription_https': (private['subscription'], 200)}
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    if (out/'requests.jsonl').exists() or (out/'summary.json').exists():
        p.error('Use a fresh output directory for each run')
    lock = threading.Lock()
    next_start = [0.0]
    rows = []
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def one(stage, index, use_proxy=True, barrier=None):
        if barrier is not None:
            barrier.wait(timeout=15)
        else:
            with lock:
                due = max(time.monotonic(), next_start[0])
                next_start[0] = due + 1/a.rps
            time.sleep(max(0, due-time.monotonic()))
        label = 'self_http' if index % 2 == 0 else 'subscription_https'
        if stage.startswith(('burst_', 'isolated_client_idle')):
            label = 'subscription_https'
        url, expected = targets[label]
        fd, tmp = tempfile.mkstemp(dir=out)
        os.close(fd)
        cmd = ['curl', '--config', '-', '--silent', '--show-error', '--retry', '0',
               '--connect-timeout', str(min(6, a.timeout)), '--max-time', str(a.timeout),
               '--max-filesize', '65536', '--output', tmp,
               '--write-out', '%{http_code}|%{time_connect}|%{time_appconnect}|%{time_starttransfer}|%{time_total}|%{size_download}']
        cmd += ['--proxy', a.proxy] if use_proxy else ['--noproxy', '*', '--interface', a.interface]
        at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            r = subprocess.run(cmd, input='url = '+json.dumps(url)+'\n', text=True,
                               capture_output=True, timeout=a.timeout+4)
            fields = r.stdout.strip().split('|')
            while len(fields) < 6:
                fields.append('0')
            body = Path(tmp).read_bytes()
            valid = r.returncode == 0 and int(fields[0] or 0) == expected
            if valid and label == 'subscription_https':
                try:
                    valid = json.loads(body)['proxies'][0]['uuid'] == node['uuid']
                except (ValueError, KeyError, IndexError, TypeError):
                    valid = False
            row = dict(at=at, stage=stage, endpoint=label, sequence=index+1,
                       ok=valid, curl_exit=r.returncode, http_status=int(fields[0] or 0),
                       proxy_socket_connect_s=float(fields[1] or 0),
                       origin_tls_complete_s=float(fields[2] or 0),
                       ttfb_s=float(fields[3] or 0), total_s=float(fields[4] or 0),
                       bytes=len(body), body_sha256=hashlib.sha256(body).hexdigest(),
                       error=redact(r.stderr.strip(), [url, ip, node['uuid']]))
        except subprocess.TimeoutExpired:
            row = dict(at=at, stage=stage, endpoint=label, sequence=index+1,
                       ok=False, curl_exit=-1, http_status=0, total_s=a.timeout+4,
                       bytes=0, error='benchmark subprocess timeout')
        finally:
            Path(tmp).unlink(missing_ok=True)
        with lock:
            rows.append(row)
            with (out/'requests.jsonl').open('a') as f:
                f.write(json.dumps(row)+'\n')
        return row

    stages = []
    def stage(name, count, workers, proxy=True):
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            measured = list(pool.map(lambda i: one(name, i, proxy), range(count)))
        s = dict(name=name, concurrency=workers, **summarize(measured))
        stages.append(s)
        print(json.dumps(s), flush=True)
        return s

    if a.mode == 'bursts':
        for concurrency in (2, 4, 8):
            measured = []
            for wave in range(4):
                barrier = threading.Barrier(concurrency)
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                    batch = list(pool.map(lambda i: one('burst_c'+str(concurrency),
                                                       wave*concurrency+i, True, barrier),
                                          range(concurrency)))
                measured.extend(batch)
                print(json.dumps(dict(concurrency=concurrency, wave=wave+1,
                                      **summarize(batch))), flush=True)
                if sum(not r['ok'] for r in batch) > max(1, concurrency//4):
                    print('Burst failure circuit breaker; no further load', flush=True)
                    break
                time.sleep(3)
            summary = dict(name='burst_c'+str(concurrency), concurrency=concurrency,
                           **summarize(measured))
            stages.append(summary)
            if summary['success_rate'] < .90:
                break
    elif a.mode == 'idle':
        for i in range(2):
            print('Independent client idle gap: '+str(a.idle_seconds)+' seconds', flush=True)
            time.sleep(a.idle_seconds)
            stage('isolated_client_idle_'+str(i+1), 4, 1)
    else:
        stage('outside_proxy_control', 6, 1, False)
        base = stage('cold_connections_c1', 20, 1)
        if base['success_rate'] >= .95:
            for concurrency, count in ((2, 24), (4, 32), (8, 48)):
                s = stage('cold_connections_c'+str(concurrency), count, concurrency)
                if s['success_rate'] < .90:
                    print('CIRCUIT BREAKER: failure rate >=10%; stopping load escalation', flush=True)
                    break
        else:
            print('BASELINE FAILED: success <95%; no concurrent load will be added', flush=True)
        for i in range(2):
            print('Idle gap: '+str(a.idle_seconds)+' seconds; next probe uses a new connection', flush=True)
            time.sleep(a.idle_seconds)
            stage('after_idle_'+str(i+1), 4, 1)
        stage('outside_proxy_control_after', 6, 1, False)
    result = dict(started_utc=started,
                  ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  proxy=a.proxy, mode=a.mode, max_start_rate_rps=a.rps if a.mode == "ramped" else None, timeout_s=a.timeout,
                  hidden_retries=False, maximum_response_bytes=65536, stages=stages,
                  note='Small-response connection stability, not maximum bandwidth or long-term uptime. Outside-proxy controls may still traverse a transparent router proxy.')
    (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
