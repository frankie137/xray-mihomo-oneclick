# Xray → mihomo 一键部署

在 Debian / Ubuntu VPS 上部署 **VLESS + REALITY + XTLS Vision**，生成 Clash Verge Rev 可导入的完整 mihomo 订阅，通过 **HTTPS + 256 位随机路径令牌**发布。无需自有域名，不依赖第三方订阅转换服务。

服务器端使用 Xray，客户端使用 mihomo；直接生成对应配置，不在服务端运行 mihomo。单用户、单节点，适合个人 VPS。

## 一键安装

要求：全新 Debian 12 / Ubuntu 22.04 或更新版本、systemd、公网 IPv4、root、curl、Python 3.10+。已在 Ubuntu 22.04 x86_64 上实测。其他系统尚未实测。

在 VPS 上执行：

```bash
curl -fsSLo /tmp/xray-mihomo-install.sh https://raw.githubusercontent.com/frankie137/xray-mihomo-oneclick/v1.0.0/install.sh && sudo bash /tmp/xray-mihomo-install.sh
```

默认通过 api.ipify.org 获取出口 IPv4（该请求会向其披露服务器 IP）。也可显式指定，避免自动检测：

```bash
sudo bash /tmp/xray-mihomo-install.sh --server-ip YOUR_PUBLIC_IPV4
```

或先审阅源码后安装：

```bash
git clone https://github.com/frankie137/xray-mihomo-oneclick.git
cd xray-mihomo-oneclick
git checkout v1.0.0
sudo bash install.sh --server-ip YOUR_PUBLIC_IPV4
```

安装会使用 apt 安装 nginx、curl、unzip、python3-venv 等依赖，从官方安装器下载 Xray，并在独立 venv 安装 Certbot。首次申请 IP 证书会以无邮箱方式注册 Let's Encrypt 账户并同意其服务条款。CA 会公开记录 IP 证书；部署脚本执行即表示接受此行为。

| TCP 端口 | 用途 | 必须放行 |
| --- | --- | --- |
| 80 | ACME HTTP-01 签发及续期验证 | 是，持续保留 |
| 443 | Xray REALITY | 是 |
| 8443 | HTTPS 订阅 | 是 |

SSH 端口保持原样。有活动 UFW 时，脚本只添加以上三条放行规则；不会启用或重置防火墙。云厂商安全组须自行放行。其他防火墙规则不会自动管理。默认端口占用或已有 Xray 时首次安装会停止，不覆盖已有业务。

自定义：

```bash
sudo bash install.sh --server-ip YOUR_PUBLIC_IPV4 --port 443 --sub-port 8443 --sni www.cloudflare.com
```

REALITY 目标需能从 VPS 访问，支持 TLS 1.3、HTTP/2，SNI 与证书匹配。默认目标不保证在所有网络可用。重复安装沿用原有状态、端口和密钥，不会套用新的端口/SNI 参数；需要迁移时请人工备份处理。

## 导入 Clash Verge Rev

在 VPS 查看个人凭据：

```bash
sudo xray-mihomo show
```

复制 `https://YOUR_PUBLIC_IPV4:8443/<随机令牌>/mihomo.yaml`，在 Clash Verge Rev 的「订阅」页面粘贴链接并导入，选中该配置，在「代理」中选择 `PROXY → VPS-REALITY`，然后按需打开系统代理或 TUN。

订阅是完整配置，使用 mihomo 支持的 JSON/YAML 1.2 格式，包含节点、DNS 和路由。局域网地址直连，其余流量默认走代理；没有默认启用中国大陆直连规则。未打开局域网代理监听，未暴露控制 API。客户端界面可能因版本不同稍有变化。

也会输出 `vless://` 分享链接，便于使用支持 REALITY 的其他客户端。

当前固定的 Xray 版本要求现代 ClientHello。订阅已显式设置 `reality-opts.support-x25519mlkem768: true`；不要在编辑节点时移除。Clash Verge Rev 内置 mihomo `1.19.32` 已通过实测；更旧内核可能需要先升级。其他客户端使用 VLESS 分享链接时也须支持相应握手。

**订阅链接和 VLESS 链接都是访问凭据。请勿提交 GitHub、发到公开 Issue 或交给第三方转换网站。** HTTPS 只保护传输；拿到订阅的人仍可使用节点。

## 管理和排错

```bash
sudo xray-mihomo status
sudo xray-mihomo show
sudo journalctl -u xray -n 60 --no-pager
sudo journalctl -u xray-mihomo-renew.service -n 60 --no-pager
sudo systemctl list-timers xray-mihomo-renew.timer
sudo /opt/xray-mihomo/acme/bin/certbot certificates
sudo /opt/xray-mihomo/acme/bin/certbot renew --dry-run --cert-name xray-mihomo
```

IP 证书使用 Let's Encrypt `shortlived` profile，有效期约 6 天。systemd 每 6 小时检查是否需要续期，续期成功后验证并重载 nginx。请保持 80 端口可达和系统时间准确。续期失败可能使订阅更新失效；REALITY 代理本身不依赖该证书。

撤销订阅 URL 并产生新令牌：

```bash
sudo xray-mihomo rotate-token
sudo xray-mihomo show
```

之后需要在客户端更新订阅地址。此操作只撤销旧订阅 URL，**不会撤销已经下载的节点 UUID**。节点凭据泄露时需要同时替换 state.json 中的 UUID 并重新运行安装、重新导入；先保存状态备份，勿在公开 Issue 粘贴该文件。

| 路径 | 内容 |
| --- | --- |
| `/etc/xray-mihomo/state.json` | root 专用，UUID、密钥、令牌 |
| `/usr/local/etc/xray/config.json` | Xray 配置，root:xray 0640 |
| `/var/lib/xray-mihomo/mihomo.yaml` | 客户端订阅，root:www-data 0640 |
| `/etc/nginx/conf.d/xray-mihomo.conf` | 专用站点，包含私密令牌 |
| `/var/backups/xray-mihomo/` | 配置快照，含敏感信息 |
| `/etc/letsencrypt/` | ACME 账户及证书私钥 |

nginx 对订阅请求关闭访问日志，未知路径返回 404；只发布客户端配置，不发布服务器私钥。Xray 拒绝访问常见内网、回环和链路本地 IP 段。服务故障自动重启；安装配置阶段失败会尝试恢复旧配置，已安装的软件包会保留。不是系统快照，也不会自动卸载依赖。

卸载时先备份状态和证书，然后停止 Xray 与 `xray-mihomo-renew.timer`，删除本项目专用 nginx 配置并执行 `nginx -t && systemctl reload nginx`，再按上表清理专用文件。**不要直接卸载 nginx 或删除整个 `/etc/letsencrypt`，以免影响其他站点。** Xray 程序的卸载请参考官方安装器。

## 版本和测试

- Xray `26.10.21`；使用官方安装器固定提交 `e42df6a772e60dd7b058f852262c4dbeb0bc231d`，校验脚本 SHA256；官方安装器再校验 Xray 发行包 SHA256。
- Certbot `5.8.0`；其传递依赖和 apt 系统包未完全锁定，安装需要访问官方软件源、GitHub、PyPI 和 ACME 服务。
- 项目脚本 MIT；Xray、mihomo、Certbot、nginx 的许可证分别由其上游管理。仓库不分发上游二进制。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n install.sh
```

CI 检查客户端/服务端参数一致、随机凭据、输入验证、订阅路径隔离、文件权限和 shell 语法。实际部署还须验证 Xray 配置、nginx 配置、HTTPS 订阅及使用真实 mihomo 内核的代理连接。安装不会修改 SSH 密码、密钥或登录策略。

2026-10-28 实测：Ubuntu 22.04 x86_64 + Xray 26.10.21；macOS arm64 上 Clash Verge Rev 内置 mihomo 1.19.32 成功通过节点访问外网，出口为 VPS；HTTPS 订阅校验成功、无效令牌返回 404、Certbot 模拟续期成功。测试不代表所有运营商及地区的网络均可达。

官方参考：[Xray 安装](https://github.com/XTLS/Xray-install)、[REALITY](https://xtls.github.io/en/config/transports/reality.html)、[mihomo VLESS](https://wiki.metacubex.one/en/config/proxies/vless/)、[IP 证书与 Certbot](https://letsencrypt.org/2026/03/11/shorter-certs-certbot/)。
