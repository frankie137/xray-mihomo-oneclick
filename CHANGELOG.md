# Changelog

All notable changes are documented here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-10-28

### Added

- A dedicated Chinese README at `README.zh-CN.md`, with language-switching links in both versions.

### Changed

- English is now the default README language, and the repository description is in English.
- Release notes and the changelog are available in English.
- Installation commands and the standalone bootstrap script are pinned to the exact `1.0.2` tag.
- Validation notes distinguish basic connectivity checks from sustained stability testing; intermittent timeouts on the test network remain under investigation.

## [1.0.1] - 2026-10-28

### Added

- Contributor guide, code of conduct, issue and pull request templates, and CODEOWNERS adapted from `opensource-template`.
- Security policy, template attribution and copyright notices, version file, and changelog.

### Changed

- README presentation with a centered title, project badges, navigation, contribution links, and licensing information.
- CI for Python 3.10, 3.12, and 3.13, plus Bash syntax, patch formatting, and restricted-file checks.
- Bootstrap downloads pinned to `v1.0.1`, retaining the previous deployment logic and service configuration.

## [1.0.0] - 2026-10-28

### Added

- One-command Xray VLESS + REALITY + XTLS Vision deployment with a complete mihomo subscription.
- HTTPS subscription delivery using Let's Encrypt IP certificates and a random path token.
- Automatic certificate renewal with systemd, configuration backups and rollback, and subscription-token rotation.
- Explicit X25519MLKEM768 support for the pinned Xray and mihomo handshake.
- Basic Ubuntu 22.04 deployment, mihomo proxy connectivity, HTTPS subscription, and certificate renewal dry-run checks.

[Unreleased]: https://github.com/frankie137/xray-mihomo-oneclick/compare/1.0.2...HEAD
[1.0.2]: https://github.com/frankie137/xray-mihomo-oneclick/compare/v1.0.1...1.0.2
[1.0.1]: https://github.com/frankie137/xray-mihomo-oneclick/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/frankie137/xray-mihomo-oneclick/releases/tag/v1.0.0
