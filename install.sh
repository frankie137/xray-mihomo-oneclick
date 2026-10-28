#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo '请以 root 运行，或使用 sudo bash install.sh' >&2
  exit 1
fi
if ! command -v python3 >/dev/null; then
  apt-get update -qq
  apt-get install -y --no-install-recommends python3 ca-certificates
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$script_dir/manager.py" ]]; then
  exec python3 "$script_dir/manager.py" install "$@"
fi
# When downloaded alone, fetch a pinned, published source revision.
revision="1.0.2"
temp_dir=$(mktemp -d)
trap 'rm -rf -- "$temp_dir"' EXIT
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  "https://raw.githubusercontent.com/frankie137/xray-mihomo-oneclick/$revision/manager.py" \
  -o "$temp_dir/manager.py"
python3 "$temp_dir/manager.py" install "$@"
