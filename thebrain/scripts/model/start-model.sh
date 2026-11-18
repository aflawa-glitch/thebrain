#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
CONFIG="$ROOT/config/local-model.env"
if [[ -f "$CONFIG" ]]; then set -a; # shellcheck disable=SC1090
  source "$CONFIG"; set +a
fi
key="$("$SCRIPT_DIR/platform_key.sh")"
# Storage root is intentionally explicit or relative to the project; never assume a named volume.
if [[ -z "${JULIAN_STORAGE_ROOT:-}" ]]; then JULIAN_STORAGE_ROOT="$(cd "$ROOT/.." && pwd)"; fi
JULIAN_STORAGE_ROOT="$(cd "$JULIAN_STORAGE_ROOT" 2>/dev/null && pwd)" || { echo "ERROR: JULIAN_STORAGE_ROOT does not exist: ${JULIAN_STORAGE_ROOT:-unset}" >&2; exit 2; }

server="${JULIAN_LLAMA_SERVER_PATH:-}"
if [[ -z "$server" ]]; then
  for candidate in \
    "$JULIAN_STORAGE_ROOT/runtimes/llama.cpp/$key/llama-server" \
    "$JULIAN_STORAGE_ROOT/runtimes/$key/bin/llama-server" \
    "$JULIAN_STORAGE_ROOT/runtimes/$key/bin/bin/llama-server" \
    "$ROOT/runtimes/$key/bin/llama-server"; do
    if [[ -x "$candidate" && ! -d "$candidate" ]]; then server="$candidate"; break; fi
  done
fi
[[ -n "$server" && -x "$server" && ! -d "$server" ]] || {
  echo "ERROR: llama-server not found or not executable for $key." >&2
  echo "Set JULIAN_LLAMA_SERVER_PATH in $CONFIG; no system/global binary will be assumed." >&2; exit 3;
}

model="${JULIAN_MODEL_PATH:-}"
if [[ -z "$model" ]]; then
  mapfile -t models < <(find "$JULIAN_STORAGE_ROOT/models" -type f \( -iname '*.gguf' \) -print 2>/dev/null | sort || true)
  if [[ ${#models[@]} -eq 1 ]]; then model="${models[0]}"
  elif [[ ${#models[@]} -eq 0 ]]; then
    echo "ERROR: no .gguf model found under $JULIAN_STORAGE_ROOT/models." >&2
    echo "Set JULIAN_MODEL_PATH to the existing Qwen GGUF file in $CONFIG." >&2; exit 4
  else
    echo "ERROR: multiple GGUF models found; select the intended Qwen model explicitly in $CONFIG:" >&2
    printf '  %s\n' "${models[@]}" >&2; exit 4
  fi
fi
[[ -f "$model" ]] || { echo "ERROR: model file does not exist: $model" >&2; exit 4; }
port="${JULIAN_LLM_PORT:-8081}"
context="${JULIAN_CONTEXT_SIZE:-4096}"
gpu_layers="${JULIAN_GPU_LAYERS:-999}"
threads="${JULIAN_THREADS:--1}"

# Prevent accidental duplicate server startup; don't kill existing processes.
if command -v curl >/dev/null 2>&1 && curl --silent --fail --max-time 2 "http://127.0.0.1:$port/v1/models" >/dev/null; then
  echo "Model endpoint already responds at http://127.0.0.1:$port/v1/models; refusing to start a duplicate server."
  exit 0
fi
mkdir -p "$JULIAN_STORAGE_ROOT/logs/julian"
log="$JULIAN_STORAGE_ROOT/logs/julian/llama-server.log"
printf 'Starting llama.cpp server\nplatform=%s\nserver=%s\nmodel=%s\nport=%s\ncontext=%s\ngpu_layers=%s\n' "$key" "$server" "$model" "$port" "$context" "$gpu_layers"
args=( -m "$model" --host 127.0.0.1 --port "$port" -c "$context" -ngl "$gpu_layers" -t "$threads" --alias "${JULIAN_LLM_MODEL:-qwen-local}" )
if [[ -n "${JULIAN_LLAMA_EXTRA_ARGS:-}" ]]; then read -r -a extra <<< "$JULIAN_LLAMA_EXTRA_ARGS"; args+=("${extra[@]}"); fi
nohup "$server" "${args[@]}" >>"$log" 2>&1 < /dev/null &
echo "$!" > "$JULIAN_STORAGE_ROOT/logs/julian/llama-server.pid"
for _ in $(seq 1 90); do
  if command -v curl >/dev/null 2>&1 && curl --silent --fail --max-time 2 "http://127.0.0.1:$port/v1/models" >/dev/null; then
    echo "PASS: model server reachable at http://127.0.0.1:$port/v1/models"
    echo "log: $log"
    exit 0
  fi
  if ! kill -0 "$(cat "$JULIAN_STORAGE_ROOT/logs/julian/llama-server.pid")" 2>/dev/null; then
    echo "ERROR: llama-server exited during startup. Inspect log: $log" >&2; tail -n 80 "$log" >&2 || true; exit 5
  fi
  sleep 1
done
echo "ERROR: llama-server did not become ready. Inspect log: $log" >&2; tail -n 80 "$log" >&2 || true; exit 6
