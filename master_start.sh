#!/usr/bin/env bash
set -Eeuo pipefail
SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PY="$SOURCE/runtimes/python/macos-arm64/python313/bin/python3.13"
exec "$PY" "$SOURCE/master_ctl.py" start "$@"
