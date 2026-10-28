# Changelog

本文件记录项目的重要改动，采用 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 格式和 [Semantic Versioning](https://semver.org/spec/v2.0.0.html) 版本号。

## [Unreleased]

## [1.0.1] - 2026-10-28

### Added

- 按指定 `opensource-template` 补齐贡献指南、行为准则、Issue/PR 模板和 CODEOWNERS。
- 增加安全政策、第三方模板版权声明、版本文件和更新记录。

### Changed

- README 使用模板的居中标题、项目徽章、导航、贡献与许可说明，保留完整中文安装和运维文档。
- CI 适配 Python 3.10、3.12、3.13，检查单元测试、Bash 语法、补丁格式及受限文件。
- 一键安装入口固定到 `v1.0.1`，部署逻辑与服务配置沿用上一版本。

## [1.0.0] - 2026-10-28

### Added

- 一键部署 Xray VLESS + REALITY + XTLS Vision，直接生成 mihomo 完整订阅。
- 使用 Let's Encrypt IP 证书和随机路径令牌，通过 HTTPS 提供订阅。
- systemd 自动续期、配置备份和失败回滚、订阅令牌轮换。
- 显式启用 X25519MLKEM768，兼容当前 Xray 与 mihomo 握手。
- 完成 Ubuntu 22.04 部署、mihomo 实际代理、HTTPS 订阅和证书模拟续期验证。

[Unreleased]: https://github.com/frankie137/xray-mihomo-oneclick/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/frankie137/xray-mihomo-oneclick/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/frankie137/xray-mihomo-oneclick/releases/tag/v1.0.0
