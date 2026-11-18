#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
CONFIG="$ROOT/config/local-model.env"
if [[ -f "$CONFIG" ]]; then set -a; # shellcheck disable=SC1090
  source "$CONFIG"; set +a
fi
storage="${JULIAN_STORAGE_ROOT:-$(cd "$ROOT/.." && pwd)}"
pidfile="$storage/logs/julian/llama-server.pid"
if [[ ! -f "$pidfile" ]]; then echo "No Julian-managed llama-server PID file found; nothing stopped."; exit 0; fi
pid="$(cat "$pidfile")"
if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  for _ in $(seq 1 10); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  if kill -0 "$pid" 2>/dev/null; then echo "ERROR: process $pid did not stop; not forcing kill." >&2; exit 2; fi
  echo "Stopped Julian-managed llama-server (PID $pid)."
else echo "Recorded llama-server process is not running."; fi
rm -f "$pidfile"
