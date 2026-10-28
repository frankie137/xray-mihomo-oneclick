<div align="center">

# 🛰️ Xray → mihomo

English | [简体中文](README.zh-CN.md)

**Deploy a REALITY node and serve an HTTPS mihomo subscription for Clash Verge Rev with one command.**

[![CI](https://github.com/frankie137/xray-mihomo-oneclick/actions/workflows/ci.yml/badge.svg)](https://github.com/frankie137/xray-mihomo-oneclick/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/frankie137/xray-mihomo-oneclick)](https://github.com/frankie137/xray-mihomo-oneclick/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](CONTRIBUTING.md)

[Quick start](#quick-start) · [Import into Clash Verge Rev](#import-into-clash-verge-rev) · [Management and troubleshooting](#management-and-troubleshooting) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

</div>

Deploy **VLESS + REALITY + XTLS Vision** on a Debian/Ubuntu VPS and generate a complete mihomo configuration for Clash Verge Rev. The subscription is served over **HTTPS with a random 256-bit path token**. No domain name or third-party subscription converter is required.

Xray runs on the server; mihomo runs on the client. The installer generates the matching client configuration directly. This project is designed for a single user and a single VPS node.

## Quick start

Requirements: a fresh Debian 12 / Ubuntu 22.04 or newer installation, systemd, a public IPv4 address, root access, curl, and Python 3.10+. Ubuntu 22.04 x86_64 has been tested; other systems have not yet been verified.

Run on your VPS:

```bash
curl -fsSLo /tmp/xray-mihomo-install.sh https://raw.githubusercontent.com/frankie137/xray-mihomo-oneclick/1.0.2/install.sh && sudo bash /tmp/xray-mihomo-install.sh
```

By default, the installer detects the outbound public IPv4 address using api.ipify.org. This request discloses the server's IP address to that service. To skip automatic detection, specify the address explicitly:

```bash
sudo bash /tmp/xray-mihomo-install.sh --server-ip YOUR_PUBLIC_IPV4
```

You can also review the source before installing:

```bash
git clone https://github.com/frankie137/xray-mihomo-oneclick.git
cd xray-mihomo-oneclick
git checkout 1.0.2
sudo bash install.sh --server-ip YOUR_PUBLIC_IPV4
```

The installer uses apt to install nginx, curl, unzip, python3-venv, and related dependencies. It downloads Xray through the official installer and installs Certbot in a dedicated virtual environment. The initial IP certificate request registers a Let's Encrypt account without an email address and accepts its terms of service. IP certificates are publicly logged by the certificate authority. Running the deployment script accepts this behavior.

| TCP port | Purpose | Must remain reachable |
| --- | --- | --- |
| 80 | ACME HTTP-01 certificate issuance and renewal | Yes |
| 443 | Xray REALITY | Yes |
| 8443 | HTTPS subscription | Yes |

The SSH port is preserved. If UFW is active, the installer adds allow rules for the three ports above; it does not enable or reset the firewall. Configure your cloud provider's security groups separately. Other firewall rules are not managed automatically. On a fresh installation, occupied ports or an existing Xray installation cause the script to stop to avoid overwriting an existing service.

Custom options:

```bash
sudo bash install.sh --server-ip YOUR_PUBLIC_IPV4 --port 443 --sub-port 8443 --sni www.cloudflare.com
```

The REALITY target must be reachable from the VPS, support TLS 1.3 and HTTP/2, and present a certificate matching the SNI. The default target may not work on every network. Reinstalling preserves the existing state, ports, and keys; new port/SNI arguments do not replace saved settings. Back up the state and handle migrations manually.

## Import into Clash Verge Rev

Display your private connection details on the VPS:

```bash
sudo xray-mihomo show
```

Copy the subscription URL, which looks like `https://YOUR_PUBLIC_IPV4:8443/<random-token>/mihomo.yaml`. Paste it into the **Profiles / Subscriptions** page in Clash Verge Rev and import it. Activate the profile, select `PROXY → VPS-REALITY`, and enable the system proxy or TUN mode as needed.

The subscription is a complete configuration in mihomo-compatible JSON/YAML 1.2 format, including the node, DNS settings, and routing rules. Private LAN destinations connect directly; other traffic uses the proxy by default. Mainland China bypass rules are not enabled by default. The configuration does not expose the local proxy to the LAN or expose a control API. UI labels may vary between client versions.

The command also prints a `vless://` share link for other clients that support REALITY.

The pinned Xray version requires a modern ClientHello. The generated subscription explicitly sets `reality-opts.support-x25519mlkem768: true`; keep this option when editing the node. Basic connectivity has been verified with mihomo `1.19.32` bundled with Clash Verge Rev. Older cores may need an update. Other clients importing the VLESS share link must also support the required handshake.

**Subscription URLs and VLESS share links are access credentials. Do not commit them to GitHub, post them in public issues, or send them to third-party converters.** HTTPS protects the transfer; anyone with the subscription can still use the node.

## Management and troubleshooting

```bash
sudo xray-mihomo status
sudo xray-mihomo show
sudo journalctl -u xray -n 60 --no-pager
sudo journalctl -u xray-mihomo-renew.service -n 60 --no-pager
sudo systemctl list-timers xray-mihomo-renew.timer
sudo /opt/xray-mihomo/acme/bin/certbot certificates
sudo /opt/xray-mihomo/acme/bin/certbot renew --dry-run --cert-name xray-mihomo
```

IP certificates use Let's Encrypt's `shortlived` profile and are valid for approximately six days. A systemd timer checks for renewal every six hours. Successful renewals validate and reload nginx. Keep TCP port 80 reachable and the system clock accurate. A failed renewal can prevent subscription updates; the REALITY proxy itself does not depend on this certificate.

Revoke the subscription URL and generate a new path token:

```bash
sudo xray-mihomo rotate-token
sudo xray-mihomo show
```

Update the URL in your client afterward. This revokes only the old subscription URL; **it does not revoke node UUIDs already downloaded by clients**. If node credentials are exposed, also replace the UUID in state.json, rerun the installer, and reimport the configuration. Back up the state first, and never paste that file into a public issue.

| Path | Contents |
| --- | --- |
| `/etc/xray-mihomo/state.json` | Root-only state: UUID, keys, and token |
| `/usr/local/etc/xray/config.json` | Xray configuration, root:xray, mode 0640 |
| `/var/lib/xray-mihomo/mihomo.yaml` | Client subscription, root:www-data, mode 0640 |
| `/etc/nginx/conf.d/xray-mihomo.conf` | Dedicated site configuration containing the private token |
| `/var/backups/xray-mihomo/` | Configuration snapshots containing sensitive data |
| `/etc/letsencrypt/` | ACME account and certificate private keys |

nginx access logging is disabled for subscription requests, and unknown paths return 404. Only the client configuration is published; server private keys are not. Xray blocks common private, loopback, and link-local destination ranges. Xray restarts after failures. If the configuration stage fails, the installer attempts to restore the previous configuration; installed packages remain. This is not a full system snapshot, and dependencies are not automatically uninstalled.

To uninstall, first back up the state and certificates. Stop Xray and `xray-mihomo-renew.timer`, remove this project's dedicated nginx configuration, and run `nginx -t && systemctl reload nginx`. Then remove the project-specific files listed above as appropriate. **Do not uninstall nginx or delete all of `/etc/letsencrypt` if other sites depend on them.** Refer to the official Xray installer for removing the Xray binary and service.

## Versions and validation

- Xray `26.10.21`, installed through official installer commit `e42df6a772e60dd7b058f852262c4dbeb0bc231d`. The script's SHA256 is checked, and the official installer verifies the Xray release archive's SHA256.
- Certbot `5.8.0`. Its transitive dependencies and apt packages are not fully locked. Installation requires access to package repositories, GitHub, PyPI, and the ACME service.
- Project scripts are MIT-licensed. Xray, mihomo, Certbot, and nginx retain their respective upstream licenses. This repository does not distribute their binaries.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n install.sh
```

CI checks matching client/server parameters, random credential generation, input validation, subscription path isolation, file permissions, and Bash syntax. Deployment validation should also cover Xray and nginx configuration checks, HTTPS subscription retrieval, and an actual proxy connection using mihomo. The installer does not change SSH passwords, keys, or login policies.

Basic checks on 2026-10-28 used Ubuntu 22.04 x86_64 with Xray 26.10.21 and Clash Verge Rev's bundled mihomo 1.19.32 on macOS arm64. Proxy requests reached the internet through the VPS, HTTPS subscription validation passed, invalid tokens returned 404, and Certbot's renewal dry run succeeded. These checks established basic connectivity. Intermittent connection timeouts were subsequently observed on the test network and remain under investigation; sustained stability has not yet been verified.

Official references: [Xray installer](https://github.com/XTLS/Xray-install), [REALITY](https://xtls.github.io/en/config/transports/reality.html), [mihomo VLESS](https://wiki.metacubex.one/en/config/proxies/vless/), and [IP certificates with Certbot](https://letsencrypt.org/2026/03/11/shorter-certs-certbot/).

A measured, bounded connection-pressure example and its limitations are available in the [2026-10-28 benchmark report](benchmarks/2026-10-28/README.md). See [benchmark tools](tools/README.md) to reproduce the tests without changing production configuration.

## Contributing

Use the [issue templates](https://github.com/frankie137/xray-mihomo-oneclick/issues/new/choose) to report bugs or suggest improvements. Read the [contributor guide](CONTRIBUTING.md) and [code of conduct](CODE_OF_CONDUCT.md) before contributing. For vulnerabilities or exposed credentials, follow the [security policy](SECURITY.md). Redact sensitive information from public reports.

## License and acknowledgments

This project is licensed under the [MIT License](LICENSE). Its repository structure and community documentation are adapted from [frankie137/opensource-template](https://github.com/frankie137/opensource-template), originally authored by Embark Studios. See [third-party notices](THIRD_PARTY_NOTICES.md) for attribution. Xray, mihomo, Certbot, and nginx retain their respective upstream licenses.
