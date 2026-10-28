# 贡献指南

欢迎为 Xray → mihomo 一键部署提交问题、文档和代码改进。项目维护者为 [@frankie137](https://github.com/frankie137)。参与前请阅读 [行为准则](CODE_OF_CONDUCT.md)。

## 报告问题

请使用 [Bug 模板](https://github.com/frankie137/xray-mihomo-oneclick/issues/new?template=bug_report.md)，说明系统、架构、脚本版本、Xray/mihomo 版本、复现步骤和预期结果。功能建议请使用 [功能模板](https://github.com/frankie137/xray-mihomo-oneclick/issues/new?template=feature_request.md)。

公开日志须移除服务器 IP、SSH 信息、UUID、密钥、short ID、订阅令牌和完整订阅 URL。不要附上 `state.json`、实际客户端配置、证书私钥或含凭据的备份。安全问题的报告方式见 [SECURITY.md](SECURITY.md)。

## 本地开发

源码使用 Python 标准库和 Bash；测试无需安装 Xray，也无需 root：

```bash
git clone https://github.com/frankie137/xray-mihomo-oneclick.git
cd xray-mihomo-oneclick
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n install.sh
git diff --check
```

Python 3.10 是部署支持的最低版本。实际安装仅支持 Debian/Ubuntu + systemd。不要在开发电脑上以 root 运行安装脚本；部署改动请使用可销毁的测试 VPS。

## 提交 Pull Request

1. Fork 仓库，从 `main` 建立工作分支。
2. 保持改动集中，解释具体问题及最终行为。Python 代码遵循 PEP 8，脚本使用明确的异常处理和权限设置。
3. 运行相关检查。改动安装、配置、续期或协议参数时，说明实际部署和 mihomo 连接验证结果；未完成的验证请如实注明。
4. 对应更新 README 或 CHANGELOG，使用虚构的示例值。
5. 使用仓库 PR 模板提交，关联相关 Issue，等待维护者审阅。

维护者发布版本时，应同步 `VERSION`、`install.sh` 的固定下载标签、README 安装命令和 CHANGELOG；先通过 CI，再为对应提交创建标签和 GitHub Release。发布包只包含 Git 跟踪的源码，并附 SHA256 校验文件。

## 贡献条款

提交贡献即表示你有权提交相关内容，并同意将其按本项目的 [MIT 许可证](LICENSE) 分发。第三方内容需标明来源并保留必要的版权与许可声明。

本指南按指定开源模板适配，来源与声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
