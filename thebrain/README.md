# TheBrain / Julian — Fresh Rebuild

A new implementation based on the project handover and roadmap. This repository was authored independently; it does not import the earlier application source as a runtime foundation or fallback.

## What is included

- FastAPI backend and a responsive ChatGPT-style white UI with fixed sidebar, chat history, multiline auto-growing composer, attachment control, process status, jump-to-latest, and stop/cancel request handling.
- One central request lifecycle: interpret → plan → registered capability → execute → verify/QC → recover/complete → explain. Structured trace events are written to SQLite.
- Capability contracts with purpose, input/output schema, permissions, side effects, timeout, cancellation support, and verification requirement.
- Registered routes for general chat, research synthesis, public URL opening, coding, file analysis, App Builder, and memory retrieval, all coordinated by the central orchestrator.
- OpenAI-compatible local inference client suitable for a local `llama-server` endpoint; no model server is bundled.
- Research provider with public-web search, direct page opening, extracted-content capture, source URL/open/read status, retrieval timestamp, source domain, optional published date, and explicit failure states.
- Deterministic verbatim-quote validator and evidence eligibility checks. It does not falsely certify a model's full factual answer; claims needing stronger proof remain a verification gap.
- Global persona/profile/language settings, per-module enablement, privacy controls, context budget setting, glossary CRUD, memory records with provenance/supersession fields, chat history, file ingestion for text/code formats, and URL input.
- Safe runtime/database path resolution, read-only update preflight, explicit database backup/restore commands, and SQLite integrity check on restore.
- Unit/API regression tests and reproducible build/test entry point `./julianrebuild.sh`.

## Requirements

- Python 3.11+ recommended.
- Optional local model server that exposes the OpenAI-compatible API (`/v1/chat/completions` and `/v1/models`).
- Network access for public-web research. If network retrieval is unavailable, Julian reports that rather than fabricating source evidence.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
./julianrebuild.sh install
./julianrebuild.sh check
./julianrebuild.sh test
./julianrebuild.sh run
```

Open `http://127.0.0.1:8080`.

## Configure a local model

Set environment variables before starting the server. Example for a llama.cpp OpenAI-compatible server:

```bash
export JULIAN_LLM_BASE_URL="http://127.0.0.1:8081/v1"
export JULIAN_LLM_MODEL="local-model"
export JULIAN_LLM_ENABLED="true"
./julianrebuild.sh run
```

The exact model identifier depends on the running server. The UI health pill checks model connectivity; a healthy web app does not imply the model is reachable.

## Configuration

| Variable | Purpose |
|---|---|
| `JULIAN_HOST` / `JULIAN_PORT` | Bind address and port (default `127.0.0.1:8080`) |
| `JULIAN_DATA_DIR` | App data directory; default is this repository's `data/` directory |
| `JULIAN_DATABASE_PATH` | Optional explicit database path; if unset, use `JULIAN_DATA_DIR/julian.sqlite3` |
| `JULIAN_LLM_BASE_URL` | OpenAI-compatible model API base URL |
| `JULIAN_LLM_MODEL` | Model identifier sent to the API |
| `JULIAN_LLM_API_KEY` | Bearer token; defaults to a local placeholder for llama.cpp |
| `JULIAN_LLM_TIMEOUT_SECONDS` | Inference timeout |
| `JULIAN_LLM_ENABLED` | Enable/disable model inference |
| `JULIAN_WEB_SEARCH_ENABLED` | Enable/disable web research |
| `JULIAN_WEB_SEARCH_TIMEOUT_SECONDS` | Search/page-open timeout |
| `JULIAN_MAX_UPLOAD_BYTES` | Upload size limit |
| `JULIAN_MAX_CONTEXT_CHARS` | Maximum assembled user/evidence context size |
| `JULIAN_ALLOW_LOCAL_FILE_URLS` | Allows non-public host targets only when explicitly enabled; keep false for ordinary use |

Settings UI values are persisted in the application database. Secrets and endpoint configuration are environment-based, not exposed in the UI.

## Data and safety

- The database path is resolved from explicit `JULIAN_DATABASE_PATH` or the configured app data directory. The application does not assume the historical Mac runtime path.
- File ingestion supports text/Markdown/source/config/log formats and text-based PDFs. Extracted PDF content retains page labels for source context. Encrypted PDFs and scanned/image-only PDFs without extractable text are rejected explicitly; OCR is not enabled.
- `save_uploaded_content=false` keeps extracted upload text in process memory for the immediate task and does not persist it to the database. It is discarded after the request.
- The local app does not include user authentication. Keep it bound to localhost unless you add an authenticated deployment boundary.
- Research can fail due to network policy, DNS, provider changes, timeouts, or inaccessible pages. Failed opens are retained as failures; search snippets are not treated as page content.
- A successful model call is not equivalent to independently verified facts. Research responses stay marked partial until semantic entailment is independently verified; quote/provenance checks alone do not certify truth.
- The update preflight is read-only. Database backup uses SQLite's online backup API; restore requires an explicit absolute path and typed confirmation, validates the backup before replacement, saves a pre-restore copy, and attempts rollback if the post-restore integrity check fails.
- The opt-in `deploy` command runs tests, stages the source, runs a health/UI smoke test before and after activation, backs up an existing target directory, and rolls back if the live smoke test fails. It requires `JULIAN_DEPLOY_CONFIRM=YES` and `JULIAN_RUNTIME_STOPPED=YES`; it refuses ambiguous database paths. It has not been run against the user's target Mac/runtime.

## Test and verification

```bash
./julianrebuild.sh check
./julianrebuild.sh test
./julianrebuild.sh preflight
```

The tests exercise contracts, routing, settings/glossary, memory provenance, quote fidelity, database initialization, and API orchestration boundaries. They do not prove a live Qwen model, live internet retrieval, browser-level UI, macOS target runtime, or true interruption behavior against every third-party model server. Those require integration/live tests in the intended runtime.

## API surface

- `GET /api/health`
- `GET /api/capabilities`
- `GET/POST /api/conversations`, `GET /api/conversations/{id}`
- `POST /api/chat`, `POST /api/chat/stream`, `POST /api/tasks/{trace_id}/cancel`
- `GET/PUT /api/settings`
- `GET/POST /api/glossary`, `DELETE /api/glossary/{term}`
- `POST /api/memories`
- `POST /api/uploads?conversation_id=...`
- `GET /api/audit/{trace_id}`, `GET /api/evidence/{trace_id}`
- `POST /api/admin/preflight`

## Project status

This is a fresh, runnable implementation and testable foundation—not a claim that every roadmap phase has been accepted. Phase 1 still requires live model/web validation, browser E2E, runtime-specific cancellation testing, robust independent claim verification, and a tested source deployment/rollback workflow before it can be marked `ACCEPTED`. Phases 2–8 are represented in the architecture and data contracts to varying degrees but are not all complete implementations.

## Safe maintenance

```bash
./julianrebuild.sh preflight
JULIAN_DATABASE_PATH="/absolute/path/to/julian.sqlite3" ./julianrebuild.sh backup "/absolute/path/to/backup-folder"
# Restore requires a verified backup, an explicit absolute target path, and typing RESTORE.
./julianrebuild.sh restore "/absolute/path/to/backup.sqlite3" "/absolute/path/to/restore-target.sqlite3"
# Deploy is opt-in; stop the target runtime and review the path/data plan first.
JULIAN_DEPLOY_CONFIRM=YES JULIAN_RUNTIME_STOPPED=YES ./julianrebuild.sh deploy "/absolute/path/to/thebrain_rebuild"
```

The deployment command is not run against the user's Mac automatically. A database outside the target's `data/` directory must be explicitly identified and reviewed; incompatible existing schemas are blocked rather than silently migrated.

## Portable USB launchers

This candidate includes a relocatable-root launcher for macOS/Linux (`launcher/julian-portable.sh`) and a PowerShell launcher for Windows (`launcher/julian-portable.ps1`). Both discover the bundle from their own location, parse `config/portable.env` as data, and refuse to fall back silently to system Python or a different model. They require the configured Python environment, `pypdf` and other dependencies, llama-server binary, and model file to exist for the host OS/CPU.

1. On macOS, run `bash scripts/configure_portable_runtime.sh` to discover existing app-owned Python/model assets and write this bundle's `config/portable.env`. It does not install packages or rewrite the environment. On other platforms, copy `config/portable.env.example` to `config/portable.env` and configure the paths manually.
2. Inspect `config/portable.env` and verify `PYTHON_PATH`, `LLAMA_SERVER_PATH`, and `MODEL_PATH` are the exact intended assets. Paths may be relative to the portable root or explicit absolute overrides.
3. Put only a compatible, tested runtime under the corresponding `runtimes/<os>-<arch>/` directory for true self-contained portability. A copied macOS environment is not assumed relocatable; stale prefixes must be diagnosed, not rewritten automatically.
4. On macOS/Linux, run `bash launcher/julian-portable.sh`. On Windows PowerShell, run `.\launcher\julian-portable.ps1` from the bundle folder.
5. The launcher is ready only after `/v1/models` and `/api/health` report healthy model/backend status. If a required runtime or model is missing, it stops and reports the exact dependency instead of claiming readiness.

The model and platform-specific runtimes are intentionally not included in this source ZIP. This ZIP therefore cannot run the full model out of the box and does not prove cross-device parity. See `PORTABLE_SUPPORT.md` and `BUILD_STATUS.md` for the verified scope and remaining acceptance gates.
