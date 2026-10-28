# Connection stability benchmark

These tools measure an existing deployment without changing Xray, nginx, firewall,
subscriptions, system proxy settings, or routing. They do not start or stop your
proxy client. Test only a VPS you control.

The test has bounded request counts, response sizes, timeouts, and concurrency.
It measures small-response connection stability, **not maximum bandwidth or a
long-term uptime SLA**. Run repeated windows at different times before judging
an intermittent problem resolved.

## Private input

Create `private/benchmark.json` locally. The `private/` directory is ignored by Git.
Use your own values; never commit this file or attach it to a public issue.

```json
{
  "subscription": "https://YOUR_VPS_IP:8443/YOUR_PRIVATE_TOKEN/mihomo.yaml",
  "profile": {
    "proxies": [
      {"server": "YOUR_VPS_IP", "uuid": "YOUR_NODE_UUID"}
    ]
  }
}
```

The subscription must point to that VPS and return a complete mihomo configuration.
The HTTP control expects this project's default `404` at the VPS HTTP root.
An unrelated website or a deployment with a different HTTP root is not an
equivalent control. Restrict the private input file to its owner, for example
with `chmod 600 private/benchmark.json` on macOS/Linux.

Use a local HTTP proxy already configured for the node under test. Prefer a
separate loopback-only test client if changing the active client would disrupt
normal use. Requests to both test endpoints must go through the intended node;
exclude these endpoints from any DIRECT bypass rules in that isolated test
client. The tools cannot verify the client's routing rules for you.

## Rate-limited requests and idle reconnects

```bash
python3 tools/stability_bench.py \
  --private-config private/benchmark.json \
  --proxy http://127.0.0.1:18891 \
  --interface en0 \
  --output private/results-ramped
```

Use the correct physical interface, such as `en0` on the tested Mac or `eth0` on
some Linux systems. Controls bypass the specified local HTTP proxy, but may
still cross a transparent router proxy. They are not proof of a clean raw path.

Default stages are 6 outside-proxy controls, 20 serial requests, 24/32/48 requests
with worker limits of 2/4/8, two 60-second idle gaps with 4 new requests each, and
6 final controls. The global start limit is 2 requests/second. A worker limit of
8 does not mean 8 connections were simultaneously active. Baseline success below
95% prevents load escalation; later failure rates above 10% stop escalation.

Each request starts a fresh curl process, uses no automatic retries, enforces a
10-second total timeout, validates TLS normally, and caps the response at 64 KiB.
Subscription responses must contain the expected UUID; bodies are not published.
The private URL is supplied through stdin instead of appearing in curl's arguments.

## Isolated client idle checks

Run this mode separately, with no other benchmark using the same test proxy:

```bash
python3 tools/stability_bench.py --mode idle --private-config private/benchmark.json --proxy http://127.0.0.1:18891 --output private/results-idle
```

It makes no test requests for 60 seconds, then starts four fresh HTTPS subscription
requests; it repeats this once. Normal user traffic may still use the VPS, so this
is client-idle verification, not proof that the server or whole network was idle.
Do not overlap another test with this mode. The report distinguishes these checks
from pauses in a stream that overlapped other test traffic.

## Simultaneous-start bursts

```bash
python3 tools/stability_bench.py \
  --mode bursts \
  --private-config private/benchmark.json \
  --proxy http://127.0.0.1:18891 \
  --output private/results-bursts
```

A thread barrier starts 2, 4, and 8 subscription requests together, with four
waves per level and a 3-second pause between waves: at most 56 requests. This
mode deliberately permits bursts instead of applying the ramped mode's start
rate. Failure thresholds stop further escalation. Keep this distinction in
published results.

Both modes write `requests.jsonl` and `summary.json`. Use a new output directory
for each invocation. Inspect outputs for private information before publishing.
Success latency percentiles exclude failed requests; failure counts and durations
are reported separately so timeouts do not disappear from the result.

## Read-only server resource sampling

On the Linux/systemd VPS, run the sampler alongside the connection tests:

```bash
sudo python3 tools/server_metrics.py --seconds 360 > /tmp/xray-resource-samples.jsonl
```

It reads `/proc` and queries the Xray PID through systemd. It does not restart,
reconfigure, install, or expose services. CPU percentages are interval samples;
short spikes between samples can be missed. Xray RSS includes shared/file-backed
pages and is not the same measurement as systemd's cgroup `MemoryCurrent`.

## Interpreting results

- Compare the same endpoints and preserve the test window, configuration, and raw data.
- Separate configured worker counts from simultaneous-start bursts.
- Separate connection latency from bandwidth; these tiny responses cannot establish Mbps capacity.
- Ping loss is ICMP loss on that probe path, not TCP retransmission or proxy request failure.
- Collect resources during failures; a passing low-load window cannot rule out every peak-load issue.
- A router proxy, VPN overlay, ISP route, and remote endpoint can change outcomes.

See the [2026-10-28 report](../benchmarks/2026-10-28/README.md) for a measured example
and its limitations.
