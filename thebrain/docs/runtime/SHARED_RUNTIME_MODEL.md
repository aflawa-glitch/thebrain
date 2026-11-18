# Julian Shared Runtime Model

## Contract

- `<shared-home>/runtimes/<os>-<arch>/python/` holds a platform-specific, managed Python distribution. Examples: `macos-arm64`, `macos-x86_64`, `windows-x86_64`, `windows-arm64`, `linux-x86_64`, `linux-arm64`.
- `<shared-home>/envs/<app-id>/` holds one isolated environment per app. Julian and future applications can use the same managed base runtime while their Python dependencies remain isolated.
- `<shared-home>/runtime-manifest.json` records relative paths and runtime/app metadata. The home is selected by `--home` or `JULIAN_RUNTIME_HOME`; without either, state defaults to the project-local `.julian-runtime` directory. Paths are resolved at runtime rather than tied to a drive letter, volume name, or home-directory assumption.
- Runtime binaries and environments are OS/architecture-specific. Do not copy a macOS venv to Windows/Linux or assume an interpreter/runtime binary can cross OS/architecture boundaries. Carry portable source/config/data; provision a compatible runtime and rebuild each app environment on the destination.
- No automatic system-Python fallback, global PATH/profile edits, sudo, Homebrew, or OS-level package changes. Missing managed runtime means a clear failure, not a silent fallback.
- No existing environment is replaced by default. `create-env --replace` stages a new environment first and preserves the previous environment under a backup name if activation succeeds.

## Layout

```text
TheBrain_Julian_Rebuild/
  .julian-runtime/
    runtimes/
      macos-arm64/python/       # staged runtime distribution, platform-specific
      linux-x86_64/python/
      windows-x86_64/python/
    envs/
      julian/                   # isolated application dependencies
      app-builder/              # isolated future application dependencies
    runtime-manifest.json
  scripts/runtime/runtime_manager.py
```

The runtime manager does not download an interpreter or silently alter the host. A trusted, compatible Python distribution must first be staged under the matching `runtimes/<platform>/python/` directory. That separation keeps runtime provisioning explicit and avoids pretending a Python venv is universally portable. After a staged environment is moved to its final path, the manager repairs and validates the venv at that final path because Python venv launchers can embed absolute paths. Apps can share the runtime home, but their environments are separate. A shared home containing native runtimes is still platform-specific; do not move a macOS runtime to Windows/Linux.

## Reuse from another application

The manager is application-agnostic. A future app can call the same manager script (or place a copy of the manager in a shared tools directory) and pass the same explicit `--home` value. Register/create an environment under a unique app ID; do not share an app's venv with another app. For example:

```bash
python /path/to/shared/tools/runtime_manager.py --home "/path/to/shared/julian-runtime" create-env invoice-app --requirements /path/to/invoice-app/requirements.txt
python /path/to/shared/tools/runtime_manager.py --home "/path/to/shared/julian-runtime" list
```

The `--home` path is the shared state contract; the manager executable itself does not need to live inside every app repository. The runtime home must be writable and should be on storage that is mounted with suitable executable permissions. A single shared home may contain multiple platform-specific runtimes, but each runtime and each environment is built for its own OS/architecture.

## Commands

Run these from the project root using the already-managed interpreter for this platform:

```bash
# Set one shared home for every app using this managed runtime:
export JULIAN_RUNTIME_HOME="/path/to/shared/julian-runtime"  # choose a writable folder on the desired storage
python scripts/runtime/runtime_manager.py doctor
python scripts/runtime/runtime_manager.py register-runtime
python scripts/runtime/runtime_manager.py create-env julian --requirements requirements.txt
python scripts/runtime/runtime_manager.py create-env app-builder --requirements path/to/app-builder-requirements.txt
python scripts/runtime/runtime_manager.py list

# Alternatively, pass --home explicitly to every command:
python scripts/runtime/runtime_manager.py --home "/path/to/shared/julian-runtime" list
```

For controlled packaging/build tests only, `--base-python /path/to/python` may be supplied explicitly. This option is not the production default; do not point it at an untrusted or mismatched interpreter. Requirements are installed into the newly staged app environment only.

## Safety and acceptance

Before rollout, back up runtime data/database/config separately from code. Run `doctor`, unit tests, API smoke, database integrity/backup checks, and live-model/live-research acceptance independently. A passing runtime-manager test does not establish that the local model, web research, browser UI, or all Phase 1 acceptance gates pass.
