#!/usr/bin/env python3
"""VLESS/REALITY + HTTPS mihomo subscription. Python standard library only."""
import argparse
import datetime
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import uuid

XRAY_VERSION = "26.10.21"
CERTBOT_VERSION = "5.8.0"
INSTALL_COMMIT = "e42df6a772e60dd7b058f852262c4dbeb0bc231d"
INSTALL_SHA256 = "954666bb028ba8561b2218372b7db76ba051f8252b2db9195321e672263aab94"
BASE = Path("/etc/xray-mihomo")
STATE = BASE / "state.json"
XRAY_CONFIG = Path("/usr/local/etc/xray/config.json")
NGINX_CONFIG = Path("/etc/nginx/conf.d/xray-mihomo.conf")
PROFILE = Path("/var/lib/xray-mihomo/mihomo.yaml")
CERT_NAME = "xray-mihomo"
CERTBOT = "/opt/xray-mihomo/acme/bin/certbot"


def run(*args, capture=False):
    return subprocess.run(args, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def write(path, text, mode=0o600, group=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            out.write(text)
        os.chmod(name, mode)
        if group:
            import grp
            os.chown(name, 0, grp.getgrnam(group).gr_gid)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate(ip, port, sub_port, sni):
    address = ipaddress.ip_address(ip)
    if address.version != 4 or not address.is_global:
        raise ValueError("需要公网 IPv4 地址")
    if not (1 <= port <= 65535 and 1 <= sub_port <= 65535):
        raise ValueError("端口必须为 1–65535")
    if len({80, port, sub_port}) != 3:
        raise ValueError("代理端口、订阅端口、HTTP 验证端口 80 必须不同")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", sni):
        raise ValueError("无效的 REALITY SNI")


def new_state(ip, port, sub_port, sni, key_output):
    fields = dict(re.findall(r"^(PrivateKey|Private key|Password \(PublicKey\)|Password|PublicKey|Public key):\s*(\S+)",
                             key_output, re.M))
    private = fields.get("PrivateKey", fields.get("Private key"))
    public = fields.get("Password (PublicKey)", fields.get("Password", fields.get("PublicKey", fields.get("Public key"))))
    if not private or not public:
        raise ValueError("无法识别 xray x25519 输出")
    return dict(ip=ip, port=port, sub_port=sub_port, sni=sni,
                uuid=str(uuid.uuid4()), private_key=private, public_key=public,
                short_id=secrets.token_hex(8), token=secrets.token_hex(32))


def xray_config(s):
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{"tag": "vless-reality", "listen": "0.0.0.0", "port": s["port"],
            "protocol": "vless", "settings": {"clients": [
                {"id": s["uuid"], "flow": "xtls-rprx-vision"}], "decryption": "none"},
            "streamSettings": {"network": "raw", "security": "reality",
                "realitySettings": {"show": False, "target": s["sni"] + ":443",
                    "xver": 0, "serverNames": [s["sni"]],
                    "privateKey": s["private_key"], "shortIds": [s["short_id"]]}}}],
        "outbounds": [{"protocol": "freedom", "tag": "direct"},
                      {"protocol": "blackhole", "tag": "blocked"}],
        "routing": {"domainStrategy": "IPOnDemand", "rules": [
            {"type": "field", "ip": ["0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10",
                "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16",
                "224.0.0.0/4", "240.0.0.0/4", "::/128", "::1/128", "fc00::/7",
                "fe80::/10", "ff00::/8"], "outboundTag": "blocked"}]}}


def mihomo_config(s):
    # JSON is valid YAML 1.2 and avoids YAML quoting/injection problems.
    return {"mixed-port": 7890, "allow-lan": False, "bind-address": "127.0.0.1",
        "mode": "rule", "log-level": "info", "ipv6": False,
        "dns": {"enable": True, "listen": "127.0.0.1:1053", "ipv6": False,
            "enhanced-mode": "fake-ip", "fake-ip-range": "198.18.0.1/16",
            "default-nameserver": ["1.1.1.1", "8.8.8.8"],
            "nameserver": ["https://1.1.1.1/dns-query", "https://8.8.8.8/dns-query"]},
        "proxies": [{"name": "VPS-REALITY", "type": "vless", "server": s["ip"],
            "port": s["port"], "uuid": s["uuid"], "network": "tcp", "udp": True,
            "tls": True, "flow": "xtls-rprx-vision", "servername": s["sni"],
            "client-fingerprint": "chrome", "packet-encoding": "xudp",
            "reality-opts": {"public-key": s["public_key"], "short-id": s["short_id"],
                             "support-x25519mlkem768": True}}],
        "proxy-groups": [{"name": "PROXY", "type": "select", "proxies": ["VPS-REALITY", "DIRECT"]}],
        "rules": ["IP-CIDR,127.0.0.0/8,DIRECT,no-resolve", "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
            "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve", "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
            "IP-CIDR,169.254.0.0/16,DIRECT,no-resolve", "MATCH,PROXY"]}


def subscription_url(s):
    return f'https://{s["ip"]}:{s["sub_port"]}/{s["token"]}/mihomo.yaml'


def vless_url(s):
    query = urllib.parse.urlencode(dict(encryption="none", flow="xtls-rprx-vision",
        security="reality", sni=s["sni"], fp="chrome", pbk=s["public_key"],
        sid=s["short_id"], type="tcp"))
    return f'vless://{s["uuid"]}@{s["ip"]}:{s["port"]}?{query}#VPS-REALITY'


def nginx_config(s, tls=True):
    config = f'''server {{
    listen 80;
    server_name {s["ip"]};
    server_tokens off;
    access_log off;
    location ^~ /.well-known/acme-challenge/ {{ root /var/lib/xray-mihomo/acme; }}
    location / {{ return 404; }}
}}
'''
    if tls:
        config += f'''server {{
    listen {s["sub_port"]} ssl;
    server_name {s["ip"]};
    server_tokens off;
    ssl_certificate /etc/letsencrypt/live/{CERT_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{CERT_NAME}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    access_log off;
    error_log /var/log/nginx/xray-mihomo-error.log crit;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
    location = /{s["token"]}/mihomo.yaml {{
        alias {PROFILE};
        default_type text/yaml;
        add_header Cache-Control "no-store" always;
        add_header profile-update-interval "24" always;
        limit_except GET {{ deny all; }}
    }}
    location / {{ return 404; }}
}}
'''
    return config


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def check_ports(ports):
    for port in ports:
        with socket.socket() as sock:
            sock.bind(("0.0.0.0", port))


def firewall(s):
    if shutil.which("ufw") and "Status: active" in run("ufw", "status", capture=True):
        for port in (80, s["port"], s["sub_port"]):
            run("ufw", "allow", f"{port}/tcp", "comment", "xray-mihomo")


def renew_units():
    write("/etc/systemd/system/xray-mihomo-renew.service", f'''[Unit]
Description=Renew Xray mihomo subscription TLS certificate
After=network-online.target nginx.service
Wants=network-online.target
[Service]
Type=oneshot
ExecStart={CERTBOT} renew --quiet --cert-name {CERT_NAME} --no-random-sleep-on-renew --deploy-hook "/usr/sbin/nginx -t && /usr/bin/systemctl reload nginx"
''', 0o644)
    write("/etc/systemd/system/xray-mihomo-renew.timer", '''[Unit]
Description=Check six-day IP certificate every six hours
[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
RandomizedDelaySec=900
Persistent=true
[Install]
WantedBy=timers.target
''', 0o644)
    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "--now", "xray-mihomo-renew.timer")


def install(args):
    ip = args.server_ip
    if not ip and not STATE.exists():
        with urllib.request.urlopen("https://api.ipify.org", timeout=15) as response:
            ip = response.read(128).decode().strip()
    first = not STATE.exists()
    if first:
        validate(ip, args.port, args.sub_port, args.sni)
        if not (BASE / ".managed").exists():
            check_ports((80, args.port, args.sub_port))
            if shutil.which("xray") or XRAY_CONFIG.exists():
                raise ValueError("发现已有 Xray，停止以避免覆盖；请先备份并人工迁移")
            BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
            write(BASE / ".managed", "xray-mihomo-oneclick\n")
    else:
        s = json.loads(STATE.read_text())
        if ip and ip != s["ip"]:
            raise ValueError("服务器 IP 与已有状态不符；请人工迁移")
        validate(s["ip"], s["port"], s["sub_port"], s["sni"])
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    run("apt-get", "update", "-qq")
    run("apt-get", "install", "-y", "--no-install-recommends", "curl", "ca-certificates",
        "unzip", "nginx", "python3-venv")
    if not Path("/usr/local/bin/xray").exists():
        url = f"https://raw.githubusercontent.com/XTLS/Xray-install/{INSTALL_COMMIT}/install-release.sh"
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != INSTALL_SHA256:
            raise ValueError("官方安装脚本 SHA256 不符，停止")
        with tempfile.NamedTemporaryFile() as script:
            script.write(data)
            script.flush()
            run("bash", script.name, "install", "--version", XRAY_VERSION,
                "--without-geodata", "--without-logfiles")
    if first:
        s = new_state(ip, args.port, args.sub_port, args.sni,
                      run("/usr/local/bin/xray", "x25519", capture=True))
        BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
        write(STATE, dump(s))
    run("python3", "-m", "venv", "/opt/xray-mihomo/acme")
    run("/opt/xray-mihomo/acme/bin/pip", "install", "--disable-pip-version-check",
        f"certbot=={CERTBOT_VERSION}")
    backup = Path("/var/backups/xray-mihomo") / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(mode=0o700, parents=True)
    for path in (XRAY_CONFIG, NGINX_CONFIG, PROFILE, STATE):
        if path.exists():
            shutil.copy2(path, backup / path.name)
    Path("/var/lib/xray-mihomo/acme").mkdir(parents=True, exist_ok=True)
    try:
        write(XRAY_CONFIG, dump(xray_config(s)), 0o640, "xray")
        run("/usr/local/bin/xray", "run", "-test", "-config", str(XRAY_CONFIG))
        write(PROFILE, dump(mihomo_config(s)), 0o640, "www-data")
        write(NGINX_CONFIG, nginx_config(s, tls=False), 0o640)
        run("nginx", "-t")
        run("systemctl", "enable", "--now", "nginx")
        run("systemctl", "reload", "nginx")
        firewall(s)
        run(CERTBOT, "certonly", "--non-interactive", "--agree-tos", "--register-unsafely-without-email",
            "--webroot", "-w", "/var/lib/xray-mihomo/acme", "--ip-address", s["ip"],
            "--required-profile", "shortlived", "--cert-name", CERT_NAME, "--keep-until-expiring")
        write(NGINX_CONFIG, nginx_config(s), 0o640)
        run("nginx", "-t")
        run("systemctl", "enable", "xray")
        run("systemctl", "restart", "xray")
        run("systemctl", "reload", "nginx")
        run("systemctl", "is-active", "--quiet", "xray", "nginx")
        renew_units()
        with urllib.request.urlopen(subscription_url(s), timeout=20) as response:
            assert json.load(response) == mihomo_config(s), "HTTPS 订阅内容不符"
    except Exception:
        for path in (XRAY_CONFIG, NGINX_CONFIG, PROFILE):
            saved = backup / path.name
            if saved.exists():
                shutil.copy2(saved, path)
            elif path.exists():
                path.unlink()
        subprocess.run(["systemctl", "restart", "xray"], check=False)
        subprocess.run(["systemctl", "reload", "nginx"], check=False)
        print(f"部署失败，配置已回滚；依赖保留。备份：{backup}", file=sys.stderr)
        raise
    write("/opt/xray-mihomo/manager.py", Path(__file__).read_text(), 0o700)
    write("/usr/local/bin/xray-mihomo", '#!/bin/sh\nexec python3 /opt/xray-mihomo/manager.py "$@"\n', 0o755)
    print("部署完成；使用 sudo xray-mihomo show 查看私密订阅。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("install")
    p.add_argument("--server-ip", default=os.environ.get("SERVER_IP"))
    p.add_argument("--port", type=int, default=443)
    p.add_argument("--sub-port", type=int, default=8443)
    p.add_argument("--sni", default="www.cloudflare.com")
    sub.add_parser("show")
    sub.add_parser("status")
    sub.add_parser("rotate-token")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("请以 root / sudo 运行")
    if args.command == "install":
        if not Path("/run/systemd/system").exists() or not shutil.which("apt-get"):
            parser.error("仅支持 Debian/Ubuntu + systemd")
    with open("/run/lock/xray-mihomo.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == "install":
            install(args)
        elif args.command == "show":
            s = json.loads(STATE.read_text())
            print("订阅（私密）：" + subscription_url(s))
            print("VLESS（私密）：" + vless_url(s))
        elif args.command == "status":
            run("systemctl", "--no-pager", "status", "xray", "nginx", "xray-mihomo-renew.timer")
        elif args.command == "rotate-token":
            s = json.loads(STATE.read_text())
            previous = dict(s)
            s["token"] = secrets.token_hex(32)
            try:
                write(NGINX_CONFIG, nginx_config(s), 0o640)
                run("nginx", "-t")
                run("systemctl", "reload", "nginx")
                write(STATE, dump(s))
            except Exception:
                write(NGINX_CONFIG, nginx_config(previous), 0o640)
                subprocess.run(["systemctl", "reload", "nginx"], check=False)
                raise
            print("旧订阅令牌已撤销；使用 xray-mihomo show 查看新链接。节点 UUID 未改变。")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"错误：{error}")
