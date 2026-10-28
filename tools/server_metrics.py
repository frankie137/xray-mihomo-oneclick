#!/usr/bin/env python3
"""Read-only Linux/systemd Xray resource sampler. Prints JSONL to stdout."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=360)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 3600:
        parser.error('seconds must be between 1 and 3600')
    pid = subprocess.check_output(
        ['systemctl', 'show', 'xray', '-p', 'MainPID', '--value'], text=True).strip()
    hz = os.sysconf('SC_CLK_TCK')
    previous_cpu = previous_process = None
    for _ in range(args.seconds):
        if not Path('/proc/' + pid + '/stat').exists():
            raise SystemExit('Original Xray process exited; stop sampling')
        now = time.monotonic()
        cpu = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
        mem = {line.split(':')[0]: int(line.split()[1])
               for line in Path('/proc/meminfo').read_text().splitlines()}
        # Parse after the parenthesized process name, which may contain spaces.
        process = Path('/proc/' + pid + '/stat').read_text().rsplit(') ', 1)[1].split()
        ticks = int(process[11]) + int(process[12])
        row = {
            'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'xray_rss_bytes': int(process[21]) * os.sysconf('SC_PAGE_SIZE'),
            'mem_available_kb': mem['MemAvailable'],
            'load1': float(Path('/proc/loadavg').read_text().split()[0]),
            'xray_fds': len(list(Path('/proc/' + pid + '/fd').iterdir())),
        }
        # Count established server sockets without publishing peer addresses.
        ports = {443: 0, 8443: 0}
        for table in ('/proc/net/tcp', '/proc/net/tcp6'):
            for line in Path(table).read_text().splitlines()[1:]:
                fields = line.split()
                port = int(fields[1].rsplit(':', 1)[1], 16)
                if fields[3] == '01' and port in ports:
                    ports[port] += 1
        row.update({'established_' + str(port): count for port, count in ports.items()})
        if previous_cpu:
            delta = sum(cpu) - sum(previous_cpu)
            idle = cpu[3] + cpu[4] - previous_cpu[3] - previous_cpu[4]
            row['host_cpu_busy_pct'] = round(100 * (1 - idle / delta), 2) if delta else 0
        if previous_process:
            row['xray_cpu_pct'] = round(
                (ticks - previous_process[1]) / hz / (now - previous_process[0]) * 100, 2)
        print(json.dumps(row), flush=True)
        previous_cpu = cpu
        previous_process = (now, ticks)
        time.sleep(1)


if __name__ == '__main__':
    main()
