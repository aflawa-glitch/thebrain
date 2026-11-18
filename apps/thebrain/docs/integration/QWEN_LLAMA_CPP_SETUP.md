# Qwen + llama.cpp integration and storage layout

This integration uses the existing Qwen GGUF and llama.cpp executable; it does not copy, download, replace, or rename them. Configure their real paths before starting. The model server is local-only (`127.0.0.1`) and exposes llama.cpp's OpenAI-compatible `/v1` API.

## Recommended single storage root

Choose one writable folder on your external drive or internal SSD. The folder name and mount point are not hardcoded. For example, if the external drive is mounted at `/Volumes/AI_Storage`, use that as `JULIAN_STORAGE_ROOT`.

```text
AI_Storage/                         # storage root; actual name/path is configurable
├── TheBrain_Julian/                # this source package / app checkout
│   ├── app/
│   ├── config/local-model.env      # local-only settings, not committed
│   └── scripts/model/
├── models/
│   └── qwen/                       # place or keep existing *.gguf here, OR set absolute JULIAN_MODEL_PATH
├── runtimes/
│   ├── macos-arm64/python/         # managed Python runtime, staged separately
│   └── llama.cpp/macos-arm64/      # existing llama-server binary, OR set absolute JULIAN_LLAMA_SERVER_PATH
├── logs/julian/                    # managed server log and PID record
└── data/julian/                    # app data/database; set JULIAN_DATA_DIR explicitly
```

This is a target layout, not an instruction to move existing files blindly. You can leave Qwen and llama.cpp where they are and set their exact paths in `config/local-model.env`. Keep the GGUF in its existing location if that avoids a large copy.

## Configure

1. Copy `config/local-model.env.example` to `config/local-model.env`.
2. Set `JULIAN_STORAGE_ROOT` to the actual shared storage folder.
3. Set `JULIAN_MODEL_PATH` to the full path of the existing Qwen `.gguf` file. If blank, auto-discovery works only when exactly one `.gguf` exists beneath `<storage-root>/models/`.
4. Set `JULIAN_LLAMA_SERVER_PATH` to the full path of the existing `llama-server` executable if it is not at `runtimes/llama.cpp/<platform>/llama-server` or a recognized legacy runtime path.
5. Confirm `JULIAN_CONTEXT_SIZE` matches the context you intend to run. Default is 4096, not an assumption that the model supports a larger context.
6. Adjust `JULIAN_GPU_LAYERS` to the amount your build/device supports. If GPU offload fails, use a tested lower value; the launcher will not silently change it.

The `.env` file is shell syntax for macOS/Linux. On Windows, use the PowerShell launcher; the same `KEY="value"` entries are read from this file. Avoid putting secrets in this file if the storage folder is shared with others.

## Start / stop on macOS and Linux

From the project root:

```bash
cp config/local-model.env.example config/local-model.env
# Edit config/local-model.env with the actual paths first.
./scripts/model/start-model.sh
```

The launcher refuses ambiguous GGUF discovery, does not kill a pre-existing endpoint, writes logs to `<storage-root>/logs/julian/llama-server.log`, and waits for `/v1/models` to respond. Stop only the process started by this launcher with:

```bash
./scripts/model/stop-model.sh
```

## Start on Windows

Copy and edit `config/local-model.env`, then run in PowerShell:

```powershell
.\scripts\model\start-model.ps1
```

The PowerShell launcher currently expects `llama-server.exe` in the configured location. Verify the exact command-line flags supported by your existing llama.cpp build if it is a customized or older build.

## Connect Julian to the model server

The application uses the OpenAI-compatible endpoint:

- Base URL: `http://127.0.0.1:8081/v1`
- Chat completions: `/chat/completions`
- Model listing / health: `/models`
- Model alias: `qwen-local` by default; configurable through `JULIAN_LLM_MODEL`.

The settings in `config/local-model.env` must be exported into the Julian process environment before starting the app. On macOS/Linux, run from the project root:

```bash
set -a
source config/local-model.env
set +a
export JULIAN_DATA_DIR="${JULIAN_DATA_DIR:-$JULIAN_STORAGE_ROOT/data/julian}"
./julianrebuild.sh run
```

Run the app using its managed app environment as described in the main README. Do not run with system Python. If the project is in a different folder, use the actual path. The app defaults to port 8080 and the model server to 8081.

## Read-only diagnosis

```bash
python3 scripts/model/model-doctor.py
```

This diagnostic only checks whether the configured local API responds. It does not start a server, modify the model, prove successful inference, or claim that Phase 1 passes. Run it with the managed Python interpreter where available.

## Safety and portability

- Do not copy a Python venv or native llama.cpp executable across OS/CPU architectures.
- The shared storage root can move between drive letters/mount points only if paths are configured dynamically or relative to the root; absolute paths in `local-model.env` must be updated when the asset moves.
- Existing model and binary assets are not modified by these scripts.
- Logs and PID files are stored under the configured storage root.
- The default bind host is loopback only. Do not expose the inference server on a LAN without adding an explicit security boundary.
- Endpoint reachability does not prove inference works. Acceptance requires an actual prompt test and response validation with the intended Qwen model.

## Create the shared folder structure without moving assets

Run from the project root with an explicit absolute path to your preferred external drive or SSD:

```bash
./scripts/model/prepare-storage.sh "/Volumes/AI_Storage"
```

Replace that example with the actual mount path. This only creates the directory skeleton; it does not move or overwrite files. Then set `JULIAN_STORAGE_ROOT` in `config/local-model.env` to the same path.
