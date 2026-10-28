# Bounded connection stability test — 2026-10-28

**Result: this short test window passed, with noticeable tail latency. It does not establish long-term stability or maximum throughput.** No fix or production configuration change was made during the run.

## Scope and environment

- Main request window: **04:50:38–04:54:23 America/Los_Angeles**, 2026-10-28 (11:50:38–11:54:23 UTC).
- VPS: Ubuntu 22.04 x86_64, 1 vCPU, approximately 705 MiB RAM; Xray 26.10.21, VLESS/REALITY/Vision on the existing port.
- Client: macOS arm64; the same mihomo 1.19.32 binary bundled with Clash Verge Rev, running as a separate loopback-only test instance. The active Clash profile, system proxy, TUN, and subscription were not changed.
- Existing router proxy and VPN-overlay state were left in place. Controls bypassed the local HTTP proxy and bound the physical interface, but may still have crossed the transparent router proxy. This was not an isolated raw-path comparison.
- Requests targeted this deployment's own HTTP root (expected 404) and HTTPS subscription (expected 200 with a matching node UUID). No third-party website was load-tested. Subscription URLs, node credentials, addresses, and response bodies are omitted.

## Connection results

In the initial window there were **200 successful HTTP requests out of 200**: **188 through the tested proxy** and **12 outside-proxy controls**. Responses totaled **196,880 application-body bytes**, excluding TCP/TLS overhead. There were no hidden retries. Every request used a new curl process; HTTPS certificate validation remained enabled.

| Stage | Requests | Success | P50 (s) | P95 (s) | Max (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Outside-proxy control, before | 6 | 6/6 | 0.751 | 1.290 | 1.389 |
| Serial cold connections | 20 | 20/20 | 0.912 | 1.767 | 1.836 |
| 2-worker cap, 2 starts/s | 24 | 24/24 | 1.571 | 3.021 | 3.499 |
| 4-worker cap, 2 starts/s | 32 | 32/32 | 1.409 | 2.913 | 4.915 |
| 8-worker cap, 2 starts/s | 48 | 48/48 | 1.174 | 2.664 | 3.712 |
| Serial-stream pause #1 (other tests active) | 4 | 4/4 | 0.694 | 0.818 | 0.832 |
| Serial-stream pause #2 (other tests active) | 4 | 4/4 | 1.179 | 2.570 | 2.787 |
| Outside-proxy control, after | 6 | 6/6 | 0.577 | 2.156 | 2.442 |
| 2 simultaneous starts × 4 waves | 8 | 8/8 | 1.581 | 3.445 | 3.903 |
| 4 simultaneous starts × 4 waves | 16 | 16/16 | 0.828 | 1.316 | 1.696 |
| 8 simultaneous starts × 4 waves | 32 | 32/32 | 0.809 | 2.796 | 4.124 |

Across the 188 proxied requests, P50 was **1.043 s**, P95 **2.762 s**, P99 **3.932 s**, and the maximum **4.915 s**. Percentiles use successful requests only; failures would be retained separately in the raw output.

The worker-capped stages are rate-limited and **must not be described as eight continuously active connections**. The separate burst stages use a thread barrier to start 2/4/8 requests together, with four waves each and a 3-second pause. Bursts used the HTTPS subscription endpoint only; the other stages alternated HTTP and HTTPS endpoints. Combined-stage latency distributions therefore mix two request types.

The initial serial-stream pauses overlapped some burst-test traffic, so those stages are not evidence of a fully idle test client. They use new connections and do not assert that a keep-alive socket survived a gap.

### Separate client-idle verification

A later, separate window at **05:03:08–05:05:17 America/Los_Angeles** made no benchmark requests on the test client for 60 seconds, then performed four fresh HTTPS subscription requests; this was repeated once. No other benchmark used that client during these pauses. All **8/8** supplementary requests succeeded; the maximum was **1.792 s**. The VPS could still carry normal user traffic, so it was not globally idle.

Including this supplementary window, totals are **208/208 HTTP requests**, of which **196/196 were proxied**. Combined proxied P50 / P95 / P99 were **1.027 / 2.733 / 3.914 s**, with a maximum of **4.915 s**. These were separate short windows, not a continuous 15-minute load test. No sustained large transfer or hours-long connection was tested.

## Resources and protocol checks

During **175 one-second samples**, from 04:52:37 to 04:55:31 local time, covering the burst and idle phases:

| Measurement | Observed |
| --- | ---: |
| Xray CPU peak | 7.97% of one core |
| Host CPU busy peak | 11.88% |
| Xray RSS peak | 45.43 MiB |
| Minimum available system memory | 447.38 MiB |
| Peak Xray file descriptors | 470 |
| Xray automatic restarts | 0 |
| Listen overflow / listen drop / backlog drop counters | 0 / 0 / 0 |

This window did not show CPU, memory, or accept-queue exhaustion. Resource sampling began after the worker-capped stages, so it does not cover the entire run or the later isolated-idle supplement. One-second sampling can miss brief spikes. RSS includes shared/file-backed pages and differs from systemd cgroup memory accounting.

A separate physical-interface Ping probe received **20/20 replies**, with 0% observed ICMP loss and RTT **168.118 / 180.149 / 252.568 ms** (min/mean/max), standard deviation **23.605 ms**. ICMP results do not measure TCP retransmissions or prove loss-free proxy traffic. Three ordinary SOCKS5 UDP → XUDP DNS checks also succeeded; no UDP throughput claim is made.

## Interpretation and limits

The node handled this bounded connection workload without observed failures. Tail latency remains material: a few successful requests took several seconds, close to timeouts observed in earlier sessions. Earlier sessions on this test network did show repeated approximately five-second connection failures. No routing or service fix was applied here, so a passing window cannot establish that the intermittent fault is resolved.

This is **not** a maximum-bandwidth, saturation, packet-loss-injection, 24-hour uptime, or SLA test. The entire main window was about four minutes, and the traffic was deliberately small. There is insufficient evidence to claim 99.9% availability or predict peak-hour behavior. Repeat windows at peak/off-peak times and obtain approval before any route change or bandwidth-saturating test.

## Reproduction and evidence

The reusable script consolidates the same procedures used for the rate-limited and separate burst runs:

```bash
python3 tools/stability_bench.py --private-config private/benchmark.json --proxy http://127.0.0.1:18891 --interface en0 --output private/ramped
python3 tools/stability_bench.py --mode bursts --private-config private/benchmark.json --proxy http://127.0.0.1:18891 --output private/bursts
# Run separately, without any other benchmark using this client:
python3 tools/stability_bench.py --mode idle --private-config private/benchmark.json --proxy http://127.0.0.1:18891 --output private/idle
```

See [tool instructions](../../tools/README.md) for private input, isolation, limits, and read-only resource sampling.

Evidence: [isolated-idle requests](requests-isolated-idle.json), [summary](summary.json), [rate-limited requests](requests-rate-limited.jsonl), [burst requests](requests-bursts.json), [latency CSV](latency-results.csv), [server samples](server-resources.jsonl), [server metadata](server-meta.json), [ICMP summary](network.json), and [UDP checks](udp-checks.json). No raw response body or private benchmark input is included.

## Methodology references

- [OpenVPN's performance troubleshooting guide](https://openvpn.net/as-docs/v3/tutorials/tutorial--vpn-performance-troubleshooting/) recommends comparing paths and observing CPU while reproducing the problem; its product-specific tuning is not applied to Xray here.
- [Xray community performance discussion #2925](https://github.com/XTLS/Xray-core/discussions/2925) illustrates why stream counts, transport, and resource observations should be recorded. Its reported throughput is not a prediction for this VPS.
- [ESnet iperf3 documentation](https://software.es.net/iperf/invoking.html) documents controlled stream and throughput tests. This run used curl small-response requests, **not iperf3**, and does not publish a bandwidth figure.

## Higher-concurrency follow-up

The [16/32/64 established-connection test](held-connections/README.md) verifies actual held connections and original-socket reuse, rather than treating the earlier eight-worker cap as a capacity limit.
