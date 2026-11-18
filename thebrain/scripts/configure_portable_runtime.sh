#!/usr/bin/env bash
# Find known app-owned runtime assets and configure the portable app for a test run.
# This script only writes this bundle's config/portable.env. It never installs packages,
# rewrites environments, modifies shell profiles, or touches the system Python.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
CONFIG="$ROOT/config/portable.env"
EXAMPLE="$ROOT/config/portable.env.example"
fail(){ printf '[Julian setup] BLOCKED: %s\n' "$*" >&2; exit 1; }
[[ -f "$ROOT/JULIAN_PORTABLE_ROOT" ]] || fail "Root marker missing: $ROOT"
[[ -f "$EXAMPLE" ]] || fail "Config example missing: $EXAMPLE"

# Discover only explicit app-owned locations; do not use system Python or silently install anything.
roots=("$ROOT" "$HOME/Documents/OTHERS/AI_Storage" "$HOME/AI_Storage")
if [[ -d /Volumes ]]; then
  while IFS= read -r p; do roots+=("$p/AI_Storage"); done < <(find /Volumes -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null)
fi
uniq_roots=(); seen='|'
for p in "${roots[@]}"; do
  [[ -d "$p" ]] || continue
  case "$seen" in *"|$p|"*) continue;; esac
  uniq_roots+=("$p"); seen+="$p|"
done

find_first(){
  local kind="$1" base candidate
  for base in "${uniq_roots[@]}"; do
    case "$kind" in
      python)
        for candidate in "$base/my_python_env/bin/python3" "$base/my_python_env/bin/python" "$base/runtimes/macos-arm64/bin/python3"; do [[ -x "$candidate" ]] && { printf '%s' "$candidate"; return 0; }; done ;;
      llama)
        for candidate in "$base/llama-b11100/llama-server" "$base/runtimes/macos-arm64/bin/llama-server" "$base/llama-server"; do [[ -x "$candidate" ]] && { printf '%s' "$candidate"; return 0; }; done ;;
      model)
        for candidate in "$base/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf" "$base/models"/*.gguf; do [[ -f "$candidate" ]] && { printf '%s' "$candidate"; return 0; }; done ;;
    esac
  done
  return 1
}
PYTHON_PATH="$(find_first python || true)"
LLAMA_SERVER_PATH="$(find_first llama || true)"
MODEL_PATH="$(find_first model || true)"
[[ -n "$PYTHON_PATH" ]] || fail "No app-owned Python runtime found. Expected $HOME/Documents/OTHERS/AI_Storage/my_python_env/bin/python3 or a bundled runtime."
[[ -n "$LLAMA_SERVER_PATH" ]] || fail "No llama-server found in discovered AI_Storage roots."
[[ -n "$MODEL_PATH" ]] || fail "No .gguf model found in discovered models folders."

printf '[Julian setup] Found Python: %s\n' "$PYTHON_PATH"
printf '[Julian setup] Found llama-server: %s\n' "$LLAMA_SERVER_PATH"
printf '[Julian setup] Found model: %s\n' "$MODEL_PATH"
if ! "$PYTHON_PATH" -c 'import fastapi, uvicorn, httpx, pypdf' >/dev/null 2>&1; then
  printf '\n[Julian setup] Required imports are missing from this exact Python runtime.\n' >&2
  printf 'No packages were installed. Run this interpreter with: -c "import fastapi,uvicorn,httpx,pypdf"\n' >&2
  exit 1
fi
cp "$EXAMPLE" "$CONFIG.tmp"
python_writer="$PYTHON_PATH"
"$python_writer" - "$CONFIG.tmp" "$PYTHON_PATH" "$LLAMA_SERVER_PATH" "$MODEL_PATH" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); text=p.read_text(encoding='utf-8')
for key,value in [('PYTHON_PATH',sys.argv[2]),('LLAMA_SERVER_PATH',sys.argv[3]),('MODEL_PATH',sys.argv[4]),('LLM_MODEL','auto')]:
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.startswith(key+'='):
            lines[i]=key+'='+value
            break
    text='\n'.join(lines)+'\n'
p.write_text(text,encoding='utf-8')
PY
mv "$CONFIG.tmp" "$CONFIG"
printf '\n[Julian setup] Config written to: %s\n' "$CONFIG"
printf '[Julian setup] No packages installed, no environment rewritten, and no global settings changed.\n'
printf '[Julian setup] Next: bash launcher/julian-portable.sh\n'
