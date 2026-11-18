#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
M=$(grep -rn -E '(^|[^A-Za-z0-9_])python3?([^A-Za-z0-9_]|$)' "$ROOT" \
    --include='*.sh' 2>/dev/null \
    | grep -v 'JULIAN_PYTHON' | grep -v 'preflight-no-system-python.sh' || true)
if [ -n "$M" ]; then
  echo "BLOCKED (D-024) — bare python3/python in scripts:"
  echo "$M"
  exit 1
fi
echo "OK: no bare python3/python invocations"
