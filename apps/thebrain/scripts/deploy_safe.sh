#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
target="$1"
[[ "${JULIAN_RUNTIME_STOPPED:-}" == "YES" ]] || { echo "BLOCKED: runtime must be stopped before deployment." >&2; exit 3; }
parent="$(dirname "$target")"
base="$(basename "$target")"
mkdir -p "$parent"
[[ ! -e "$target" || -d "$target" ]] || { echo "BLOCKED: target exists and is not a directory." >&2; exit 3; }
[[ "$target" != "$ROOT" && "$target" != "/" ]] || { echo "BLOCKED: unsafe target path." >&2; exit 3; }
if [[ -d "$target" ]]; then
  while IFS= read -r dbfile; do
    [[ -n "$dbfile" ]] || continue
    case "$dbfile" in
      "$target"/data/*) ;;
      *)
        if [[ -z "${JULIAN_DATABASE_PATH:-}" || "${JULIAN_DATABASE_PATH}" == "$target"/* ]]; then
          echo "BLOCKED: database found outside target/data: $dbfile. Set JULIAN_DATABASE_PATH to a verified external path and complete a data/schema migration review before deployment." >&2
          exit 4
        fi
        ;;
    esac
  done < <(find "$target" -type f \( -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' \) -print)
fi

# Prove the candidate source is internally testable before touching the target.
cd "$ROOT"
"$PYTHON_BIN" -m compileall -q app tests main.py
"$PYTHON_BIN" -m pytest -q

stamp="$(date +%Y%m%d_%H%M%S)"
stage="$parent/.${base}.stage.$$"
backup="$parent/${base}.backup.${stamp}"
failed="$parent/${base}.failed.${stamp}"
cleanup() { [[ -d "$stage" ]] && rm -rf "$stage" || true; }
trap cleanup EXIT
mkdir -p "$stage"
# Exclude runtime state, secrets, virtual environments, logs and generated test artifacts.
tar -C "$ROOT" --exclude='./.git' --exclude='./.venv' --exclude='./__pycache__' --exclude='./.pytest_cache' --exclude='./data' --exclude='./logs' --exclude='./backups' --exclude='./.env' -cf - . | tar -C "$stage" -xf -
# Preserve the target's app-local data directory if it exists; no database is migrated or overwritten by this copy.
if [[ -d "$target/data" && ! -e "$stage/data" ]]; then cp -a "$target/data" "$stage/data"; fi

smoke() {
  local dir="$1" port pid smoke_data log
  port="$("$PYTHON_BIN" - <<'PORTFIND'
import socket
s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()
PORTFIND
)"
  smoke_data="$(mktemp -d "${TMPDIR:-/tmp}/julian-smoke-data.XXXXXX")"
  log="$(mktemp "${TMPDIR:-/tmp}/julian-smoke-log.XXXXXX")"
  pushd "$dir" >/dev/null
  JULIAN_PORT="$port" JULIAN_HOST=127.0.0.1 JULIAN_DATA_DIR="$smoke_data" JULIAN_DATABASE_PATH= JULIAN_LLM_ENABLED=false "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "$port" >"$log" 2>&1 &
  pid=$!
  popd >/dev/null
  for _ in $(seq 1 40); do
    if "$PYTHON_BIN" - "$port" <<'HEALTHCHECK' >/dev/null 2>&1
import sys,urllib.request,json
port=sys.argv[1]
with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=1) as r:
    data=json.load(r)
    assert r.status == 200 and data.get('status') in ('ok','degraded') and data.get('database',{}).get('status') == 'initialized'
with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=1) as r:
    assert r.status == 200 and b'TheBrain / Julian' in r.read()
HEALTHCHECK
    then
      kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
      rm -rf "$smoke_data"; rm -f "$log"
      return 0
    fi
    sleep 0.25
  done
  kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
  echo "FAIL: deployment smoke test failed for $dir; log: $log" >&2
  cat "$log" >&2 || true
  rm -rf "$smoke_data"
  return 1
}

smoke "$stage"
if [[ -e "$target" ]]; then mv "$target" "$backup"; fi
if ! mv "$stage" "$target"; then
  [[ -e "$backup" ]] && mv "$backup" "$target"
  echo "FAIL: stage activation failed; original target restored." >&2
  exit 5
fi
if ! smoke "$target"; then
  mv "$target" "$failed"
  if [[ -e "$backup" ]]; then mv "$backup" "$target"; else rm -rf "$target"; fi
  echo "FAIL: live smoke test failed; previous target restored when one existed. Failed build preserved at $failed" >&2
  exit 6
fi
if [[ -e "$backup" ]]; then echo "PASS: deployment verified. Previous target backup: $backup"; else echo "PASS: deployment verified. No previous target existed."; fi
