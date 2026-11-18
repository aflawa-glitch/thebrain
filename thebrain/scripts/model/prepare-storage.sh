#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $# -ne 1 ]]; then echo "Usage: $0 <absolute-storage-root>" >&2; exit 2; fi
storage="$1"
[[ "$storage" = /* ]] || { echo "Provide an absolute storage root path; relative paths are refused." >&2; exit 2; }
mkdir -p "$storage"/{apps,models/qwen,runtimes/llama.cpp,runtimes/python,.julian-runtime,logs/julian,data/julian,backups/julian}
cat <<EOF2
Prepared folder structure at:
  $storage

Created directories only; no existing models, runtimes, application source, or data were moved or overwritten.
Next:
  1. Put/keep the Julian project under $storage/apps/TheBrain_Julian (or another app folder).
  2. Keep the existing Qwen GGUF wherever it currently lives, or place it in $storage/models/qwen.
  3. Keep the existing llama-server wherever it currently lives, or place it in $storage/runtimes/llama.cpp/<platform>/.
  4. Configure JULIAN_STORAGE_ROOT, JULIAN_MODEL_PATH, and JULIAN_LLAMA_SERVER_PATH in the app's config/local-model.env.
EOF2
