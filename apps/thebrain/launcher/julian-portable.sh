#!/usr/bin/env bash
# Relocatable Julian launcher for macOS/Linux. Never changes global OS settings.
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
CONFIG="${JULIAN_PORTABLE_CONFIG:-$ROOT/config/portable.env}"
fail(){ printf '[Julian] BLOCKED: %s\n' "$*" >&2; exit 1; }
info(){ printf '[Julian] %s\n' "$*"; }
[[ -f "$ROOT/JULIAN_PORTABLE_ROOT" ]] || fail "Portable root marker missing: $ROOT/JULIAN_PORTABLE_ROOT"
[[ -f "$ROOT/main.py" && -f "$ROOT/app/main.py" ]] || fail "Julian application files missing under discovered root: $ROOT"
[[ -f "$CONFIG" ]] || fail "Config missing: $CONFIG. Copy config/portable.env.example to config/portable.env and edit it."
# Parse KEY=VALUE as data; never source/eval a configuration file.
cfg() {
  local key="$1"
  awk -v key="$key" '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    { line=$0; sub(/^[[:space:]]*/, "", line); split(line, a, "="); if (a[1] == key) { sub(/^[^=]*=/, "", line); sub(/[[:space:]]*$/, "", line); print line; exit } }
  ' "$CONFIG"
}
resolve_path() { local value="$1"; [[ -n "$value" ]] || return 1; case "$value" in /*) printf '%s' "$value" ;; *) printf '%s/%s' "$ROOT" "$value" ;; esac; }
truthy(){ local v; v="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"; [[ "$v" == "true" || "$v" == "1" || "$v" == "yes" || "$v" == "on" ]]; }
PYTHON_PATH="$(resolve_path "${JULIAN_PYTHON_PATH:-$(cfg PYTHON_PATH)}")" || fail "PYTHON_PATH is empty."
LLAMA_SERVER_PATH="$(resolve_path "${JULIAN_LLAMA_SERVER_PATH:-$(cfg LLAMA_SERVER_PATH)}")" || fail "LLAMA_SERVER_PATH is empty."
MODEL_PATH="$(resolve_path "${JULIAN_MODEL_PATH:-$(cfg MODEL_PATH)}")" || fail "MODEL_PATH is empty."
LLM_HOST="${JULIAN_LLM_HOST:-$(cfg LLM_HOST)}"; LLM_PORT="${JULIAN_LLM_PORT:-$(cfg LLM_PORT)}"; LLM_MODEL="${JULIAN_LLM_MODEL:-$(cfg LLM_MODEL)}"; LLM_MODEL="${JULIAN_LLM_MODEL:-$(cfg LLM_MODEL)}"
APP_HOST="${JULIAN_HOST:-$(cfg APP_HOST)}"; APP_PORT="${JULIAN_PORT:-$(cfg APP_PORT)}"
CONTEXT_SIZE="${JULIAN_CONTEXT_SIZE:-$(cfg CONTEXT_SIZE)}"; GPU_LAYERS="${JULIAN_GPU_LAYERS:-$(cfg GPU_LAYERS)}"
LLM_ENABLED="${JULIAN_LLM_ENABLED:-$(cfg LLM_ENABLED)}"; WEB_SEARCH_ENABLED="${JULIAN_WEB_SEARCH_ENABLED:-$(cfg WEB_SEARCH_ENABLED)}"
OPEN_BROWSER="${JULIAN_OPEN_BROWSER:-$(cfg OPEN_BROWSER)}"; STARTUP_TIMEOUT="${JULIAN_STARTUP_TIMEOUT_SECONDS:-$(cfg STARTUP_TIMEOUT_SECONDS)}"
DATA_VALUE="${JULIAN_DATA_DIR:-$(cfg DATA_DIR)}"; LOG_VALUE="${JULIAN_LOG_DIR:-$(cfg LOG_DIR)}"
DATA_DIR="$(resolve_path "$DATA_VALUE")"; LOG_DIR="$(resolve_path "$LOG_VALUE")"
[[ -x "$PYTHON_PATH" ]] || fail "Configured Python runtime is missing or not executable: $PYTHON_PATH. No system-Python fallback was attempted."
"$PYTHON_PATH" -c 'import fastapi, uvicorn, httpx, pypdf' >/dev/null 2>&1 || fail "Required dependencies are missing in $PYTHON_PATH (FastAPI, Uvicorn, HTTPX, pypdf). No automatic installation was attempted."
truthy "$LLM_ENABLED" || fail "LLM_ENABLED is false. Portable launch refuses a silent quality downgrade; configure a compatible local model runtime."
[[ -x "$LLAMA_SERVER_PATH" ]] || fail "Configured llama-server is missing or not executable: $LLAMA_SERVER_PATH"
[[ -f "$MODEL_PATH" ]] || fail "Configured model file is missing: $MODEL_PATH"
[[ "$LLM_PORT" =~ ^[0-9]+$ && "$APP_PORT" =~ ^[0-9]+$ && "$CONTEXT_SIZE" =~ ^[0-9]+$ ]] || fail "Port/context settings must be numeric."
[[ "$LLM_PORT" != "$APP_PORT" ]] || fail "LLM_PORT and APP_PORT must differ."
[[ "$STARTUP_TIMEOUT" =~ ^[0-9]+$ ]] && (( STARTUP_TIMEOUT > 0 )) || fail "STARTUP_TIMEOUT_SECONDS must be a positive integer."
mkdir -p "$DATA_DIR" "$LOG_DIR" "$ROOT/cache" "$ROOT/backups"
export JULIAN_HOST="$APP_HOST" JULIAN_PORT="$APP_PORT" JULIAN_DATA_DIR="$DATA_DIR"
export JULIAN_LLM_BASE_URL="http://${LLM_HOST}:${LLM_PORT}/v1" JULIAN_LLM_ENABLED=true JULIAN_WEB_SEARCH_ENABLED="$WEB_SEARCH_ENABLED"
export JULIAN_PORTABLE_ROOT="$ROOT"
LLM_LOG="$LOG_DIR/llama-server.log"; APP_LOG="$LOG_DIR/julian-backend.log"
LLM_PID=""; APP_PID=""
cleanup() {
  trap - INT TERM EXIT
  if [[ -n "$APP_PID" ]] && kill -0 "$APP_PID" 2>/dev/null; then kill "$APP_PID" 2>/dev/null || true; wait "$APP_PID" 2>/dev/null || true; fi
  if [[ -n "$LLM_PID" ]] && kill -0 "$LLM_PID" 2>/dev/null; then kill "$LLM_PID" 2>/dev/null || true; wait "$LLM_PID" 2>/dev/null || true; fi
  info "Stopped only the processes started by this launcher."
}
trap cleanup INT TERM EXIT
port_available() {
  "$PYTHON_PATH" - "$1" <<'PY'
import socket,sys
s=socket.socket()
try: s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError: raise SystemExit(1)
finally: s.close()
PY
}
port_available "$LLM_PORT" || fail "LLM port $LLM_PORT is occupied. No process was killed."
port_available "$APP_PORT" || fail "App port $APP_PORT is occupied. No process was killed."
info "Portable root: $ROOT"; info "Python: $PYTHON_PATH"; info "Model: $MODEL_PATH"
info "Starting local model server..."
"$LLAMA_SERVER_PATH" -m "$MODEL_PATH" --host "$LLM_HOST" --port "$LLM_PORT" -c "$CONTEXT_SIZE" --n-gpu-layers "$GPU_LAYERS" >"$LLM_LOG" 2>&1 &
LLM_PID=$!
ready=0
for ((i=0; i<STARTUP_TIMEOUT; i++)); do
  kill -0 "$LLM_PID" 2>/dev/null || fail "llama-server exited. Inspect $LLM_LOG"
  if curl -fsS --max-time 2 "http://${LLM_HOST}:${LLM_PORT}/v1/models" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[[ "$ready" == 1 ]] || fail "Model API did not become ready within ${STARTUP_TIMEOUT}s. Inspect $LLM_LOG"
if [[ "$LLM_MODEL" == "auto" || -z "$LLM_MODEL" ]]; then
  LLM_MODEL="$("$PYTHON_PATH" - "http://${LLM_HOST}:${LLM_PORT}/v1/models" <<'PYMODEL'
import json,sys,urllib.request
try:
 with urllib.request.urlopen(sys.argv[1],timeout=5) as r: data=json.load(r).get("data",[])
 print(data[0].get("id", "") if data else "")
except Exception: print("")
PYMODEL
)"
  [[ -n "$LLM_MODEL" ]] || fail "Model server is healthy but did not report a model identifier at /v1/models. Set LLM_MODEL explicitly after checking the server."
fi
export JULIAN_LLM_MODEL="$LLM_MODEL"
info "Model API ready; configured model identifier: $LLM_MODEL"
info "Starting Julian backend..."
cd "$ROOT"
PYTHONPATH="$ROOT" "$PYTHON_PATH" -m uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT" >"$APP_LOG" 2>&1 &
APP_PID=$!
ready=0
for ((i=0; i<STARTUP_TIMEOUT; i++)); do
  kill -0 "$APP_PID" 2>/dev/null || fail "Julian backend exited. Inspect $APP_LOG"
  if curl -fsS --max-time 2 "http://${APP_HOST}:${APP_PORT}/api/health" >"$ROOT/cache/health-check.json" 2>/dev/null; then
    if "$PYTHON_PATH" - "$ROOT/cache/health-check.json" <<'PY'
import json,sys
try:
 d=json.load(open(sys.argv[1],encoding="utf-8"))
 raise SystemExit(0 if d.get("status")=="ok" and d.get("model",{}).get("status")=="reachable" else 1)
except Exception: raise SystemExit(1)
PY
    then ready=1; break; fi
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || fail "Backend/model health did not pass. Inspect $APP_LOG and $LLM_LOG; the app alone is not considered ready."
info "READY: UI http://${APP_HOST}:${APP_PORT}/"; info "Press Ctrl+C to stop Julian and the model server."
if truthy "$OPEN_BROWSER"; then
  if command -v open >/dev/null 2>&1; then open "http://${APP_HOST}:${APP_PORT}/" || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://${APP_HOST}:${APP_PORT}/" >/dev/null 2>&1 || true; fi
fi
while kill -0 "$APP_PID" 2>/dev/null; do
  kill -0 "$LLM_PID" 2>/dev/null || fail "Model server stopped unexpectedly. Inspect $LLM_LOG"
  sleep 1
done
wait "$APP_PID"
