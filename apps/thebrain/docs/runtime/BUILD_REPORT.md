# Runtime rebuild verification report

## Scope completed

- Added a runtime manager that detects OS/CPU architecture dynamically and resolves all managed runtime/environment paths relative to the project root.
- Added a configurable shared runtime home (`--home` or `JULIAN_RUNTIME_HOME`) so multiple application projects can use the same managed platform runtime and manifest while maintaining isolated environments per app (`julian`, `app-builder`, future app IDs).
- Added explicit runtime registration/manifest, environment listing, non-mutating doctor checks, app-id path-traversal validation, staged environment creation, final-path venv repair/validation, and opt-in replacement preserving the previous environment.
- Updated macOS/Linux shell entry points and added a Windows PowerShell runtime entry point. Application commands no longer silently fall back to system Python when a managed environment/runtime is absent.
- Updated README and added the runtime architecture contract.

## Verification performed in build workspace

- `PYTHON_BIN=<build interpreter> ./julianrebuild.sh check`: PASS.
- `PYTHON_BIN=<build interpreter> ./julianrebuild.sh test`: PASS, 35 passed, 6 subtests passed.
- Created a temporary isolated environment with explicit `--base-python`, verified `sys.prefix != sys.base_prefix`, and inspected generated manifest: PASS.
- Verified missing managed runtime returns a clear not-ready diagnostic rather than silently using system Python: PASS (expected fail-closed status).
- `bash -n` on shell entry points and Python `compileall`: PASS.
- Shared-home path selection and real environment creation/final-path validation: PASS.
- Duplicate app environment creation is rejected unless explicit `--replace` is supplied: PASS.

## Boundaries / not claimed

- This source archive does **not** include a redistributable Python runtime binary for macOS, Windows, or Linux. A trusted, matching runtime distribution must be staged under `<JULIAN_RUNTIME_HOME>/runtimes/<os>-<arch>/python/` (or the project-local `.julian-runtime/runtimes/...` default) before a clean-machine bootstrap. This was left explicit rather than downloading or bundling an unverified runtime.
- The actual user's Mac runtime was not modified or directly tested from this Linux build workspace. macOS ARM64, macOS x86-64, Windows, and Linux ARM64 need target-platform verification.
- Local model connectivity, live web research, browser E2E, mobile layout, and stronger independent semantic claim verification remain open Phase 1 acceptance gates.
- Existing DB/model/config/user data are not included or overwritten by this source rebuild.

Phase 1 remains ACTIVE, not ACCEPTED.
