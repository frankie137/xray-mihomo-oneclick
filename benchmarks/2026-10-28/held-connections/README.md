# Established-connection follow-up — 2026-10-28

The deployment passed **16, 32, and 64 simultaneous held connections**, three waves per level. This is the highest level tested, not a measured capacity ceiling or a user count. Load escalation ended at the owner's request.

## Method

The same isolated loopback-only mihomo client and existing VLESS/REALITY/Vision node were used. No production client, subscription, route, or server configuration was changed. Each barrier-started worker established an authenticated HTTPS subscription connection through the proxy, validated the response, and held the original socket for at least 15 seconds after all workers finished setup. It then requested the same resource again on that socket, with automatic socket reopening disabled. Every second during the hold, the isolated mihomo controller reported exactly the target number of connections: 16/16, 32/32, or 64/64 in every wave. These are small responses, not sustained bandwidth transfers.

Measured window: **12:18:33–12:24:56 UTC** (05:18:33–05:24:56 America/Los_Angeles). There were **336 established connections and 672 successful HTTP requests** in the main stages. A separate one-connection preflight is excluded. An initial 64-worker invocation was blocked locally by the execution sandbox before network access; its immediate permission errors are excluded from VPS results, and the full level was rerun with network access.

| Held concurrently | Initial requests | Original-socket second requests | Setup P50 (s) | Setup P95 (s) | Setup max (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16 | 48/48 | 48/48 | 1.084 | 2.781 | 4.703 |
| 32 | 96/96 | 96/96 | 1.362 | 3.345 | 4.596 |
| 64 | 192/192 | 192/192 | 1.138 | 1.490 | 1.830 |

Setup includes proxy negotiation, TLS, and the first response. Latency percentiles are interpolated over successful connections; no request failed in these main stages. Client controller samples are preserved in each level's summary. Server socket counts include background user traffic and must not be substituted for isolated-client counts.

## Resource observations

The read-only sampler recorded 415 samples at approximately one-second intervals, 12:18:27–12:25:24 UTC. Xray CPU peaked at **15.94% of one core**, host CPU busy at **24.75%**, Xray RSS at **55.95 MiB**, and minimum available system memory was **440.41 MiB**. Established server sockets on the HTTPS subscription port peaked at **64**. Xray remained active with its original process and zero automatic restarts. These are sampled values; sub-second peaks can be missed. RSS differs from cgroup memory accounting.

There was no observed CPU or memory exhaustion in this workload. This does not rule out bandwidth limits, congested routes, multi-minute idle expiry, or earlier intermittent timeouts. Existing router proxy and VPN-overlay state were retained. The self-hosted endpoint tests the proxy path but does not represent every external destination. No fix was deployed, and earlier intermittent failures remain unresolved.

## Reproduce and evidence

See [tool instructions](../../../tools/README.md). Run only against your own deployment, through an isolated test client. Stop escalation when failures or resource pressure appear.

```bash
python3 tools/concurrency_bench.py --private-config private/benchmark.json --levels 16 32 64 --waves 3 --hold-seconds 15 --output private/held-connections
```

Evidence: [combined summary](summary.json), [16 connections](connections-16.jsonl), [32 connections](connections-32.jsonl), [64 connections](connections-64.jsonl), [16 controller samples](summary-16.json), [32 controller samples](summary-32.json), [64 controller samples](summary-64.json), and [server samples](server-resources.jsonl). No credentials, private URL, peer addresses, or response bodies are published.
