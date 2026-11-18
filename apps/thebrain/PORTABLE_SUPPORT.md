# Portable Runtime Support — Evidence Status

## Portable packaging behavior implemented

- Root discovery is based on the launcher location and `JULIAN_PORTABLE_ROOT`, not the drive letter, volume name, username, or working directory.
- Python, llama-server, model, data, logs, cache, and backups are configured relative to the bundle root by default; explicit absolute paths are allowed only as deliberate overrides.
- Configuration is parsed as data; it is not sourced/evaluated as shell or PowerShell code.
- No automatic package installation, environment recreation, system Python fallback, global PATH/profile changes, sudo, registry edits, or process killing.
- The launcher refuses to report readiness unless both the model API and Julian backend health checks pass.
- Shutdown targets only process IDs started by the launcher.
- The Python app and database remain independent of the launcher; data is under the portable root by default.

## Platform verification matrix

| Platform | Launcher | Current verification status |
|---|---|---|
| macOS ARM64 | Bash | Shell syntax checked in Linux container; not executed on the user's M1, and bundled runtime/model are not included |
| macOS x86_64 | Bash | Not live-verified |
| Linux x86_64/ARM64 | Bash | Shell syntax checked only; not live-verified |
| Windows x86_64/ARM64 | PowerShell | Script authored but not syntax- or runtime-tested in Windows PowerShell |
| Android/iOS/other devices | None | Not supported by this package; do not claim universal-device compatibility |

The model file and platform-specific Python/llama.cpp binaries are intentionally not bundled. They are large, OS/CPU-specific artifacts and cannot safely be treated as interchangeable. Configure and validate the matching runtime for each target. This package does not silently downgrade the model or verification policy.

## Remaining acceptance gates

- Test the actual relocated bundle on the user's M1 with the chosen Python environment, `pypdf` dependency, llama-server, and configured Qwen model.
- Verify model inference, live search/page opening, quote fidelity, historical-date tests, cancellation, uploads, history, and browser UX end-to-end.
- Test relocation to a second supported host/OS and Windows PowerShell syntax/runtime before calling those platforms supported.
- Fault-inject updater failures and verify rollback against a disposable copy of the actual runtime/data layout.

Status: **portable launch architecture implemented; platform portability and full Phase 1 acceptance are not yet proven.**
