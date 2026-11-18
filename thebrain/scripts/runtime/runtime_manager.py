#!/usr/bin/env python3
"""Managed shared Python runtime and isolated per-application environments.

Set JULIAN_RUNTIME_HOME or pass --home to share one managed runtime registry across
multiple applications. No host PATH/profile edits, sudo, package-manager mutation,
or implicit system-Python fallback. Stage a trusted compatible interpreter under
<home>/runtimes/<platform>/python; each app gets its own environment under <home>/envs/<app-id>.
"""
from __future__ import annotations
import argparse, json, os, platform, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from typing import Any

VERSION = "1.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# A shared runtime home can be set once for multiple applications. Keep the default
# project-local for zero-configuration use; never mutate host PATH/profile settings.
STATE_ROOT = Path(os.environ.get("JULIAN_RUNTIME_HOME", PROJECT_ROOT / ".julian-runtime")).expanduser().resolve()
RUNTIMES = STATE_ROOT / "runtimes"
ENVS = STATE_ROOT / "envs"
MANIFEST = STATE_ROOT / "runtime-manifest.json"


def configure_home(value: str | None) -> None:
    """Set a shared managed runtime home before a command performs filesystem work."""
    global STATE_ROOT, RUNTIMES, ENVS, MANIFEST
    if value:
        STATE_ROOT = Path(value).expanduser().resolve()
        RUNTIMES = STATE_ROOT / "runtimes"
        ENVS = STATE_ROOT / "envs"
        MANIFEST = STATE_ROOT / "runtime-manifest.json"


def platform_key() -> str:
    system = platform.system().lower()
    system = {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(system, system)
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)
    return f"{system}-{machine}"


def app_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}", value):
        raise ValueError("app id must be 1-64 characters: letters, numbers, dot, underscore, hyphen; start alphanumeric")
    if value in {".", ".."}:
        raise ValueError("invalid app id")
    return value


def runtime_python() -> Path:
    root = RUNTIMES / platform_key() / "python"
    candidates = [root / "bin" / "python3", root / "bin" / "python", root / "python.exe"]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise FileNotFoundError(
        f"No managed Python runtime for {platform_key()} at {root}. "
        "Stage a compatible runtime there; system Python fallback is intentionally disabled."
    )


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check)


def python_info(python: Path) -> dict[str, Any]:
    code = "import json,platform,sys; s={'darwin':'macos','win32':'windows','linux':'linux'}.get(sys.platform,sys.platform); m=platform.machine().lower(); m={'amd64':'x86_64','x64':'x86_64','aarch64':'arm64','arm64':'arm64'}.get(m,m); print(json.dumps({'executable':sys.executable,'version':platform.python_version(),'prefix':sys.prefix,'base_prefix':sys.base_prefix,'implementation':platform.python_implementation(),'machine':platform.machine(),'platform':sys.platform,'platform_key':s+'-'+m}))"
    result = run([str(python), "-c", code])
    return json.loads(result.stdout.strip().splitlines()[-1])


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.exists():
        return {"schema_version": 1, "manager_version": VERSION, "runtimes": {}, "applications": {}}
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported runtime manifest schema: {data.get('schema_version')!r}; no writes performed")
    return data


def managed_runtime_info() -> tuple[Path, dict[str, Any]]:
    py = runtime_python()
    info = python_info(py)
    if info["platform_key"] != platform_key():
        raise RuntimeError(f"Runtime platform mismatch: expected {platform_key()}, got {info['platform_key']}")
    return py, info


def cmd_doctor(_args: argparse.Namespace) -> int:
    print(f"Julian Runtime Manager {VERSION}")
    print(f"project_root: {PROJECT_ROOT}")
    print(f"state_root: {STATE_ROOT}")
    print(f"host_platform: {platform_key()}")
    print(f"manager_python: {sys.executable}")
    try:
        py, info = managed_runtime_info()
        print(f"managed_runtime: {py}")
        print(f"runtime_version: {info['version']}")
        print("status: ready")
        return 0
    except Exception as exc:
        print(f"status: not_ready ({exc})")
        return 2


def cmd_register(args: argparse.Namespace) -> int:
    py, info = managed_runtime_info()
    manifest = load_manifest()
    rel = py.relative_to(STATE_ROOT).as_posix()
    manifest["runtimes"][platform_key()] = {"python_relative_path": rel, "python_version": info["version"], "implementation": info["implementation"], "registered_by_manager": VERSION}
    atomic_json(MANIFEST, manifest)
    print(f"registered_runtime: {rel} ({info['version']})")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    manifest = load_manifest()
    print(json.dumps({"host_platform": platform_key(), "runtimes": manifest.get("runtimes", {}), "applications": manifest.get("applications", {})}, indent=2))
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    name = app_id(args.app_id)
    # Production default: only use a managed runtime staged under the Julian root.
    py = Path(args.base_python).expanduser().resolve() if args.base_python else runtime_python()
    if not py.is_file() or not os.access(py, os.X_OK):
        raise FileNotFoundError(f"Base interpreter is not runnable: {py}")
    info = python_info(py)
    if info["platform_key"] != platform_key():
        raise RuntimeError("Base interpreter platform does not match this host")
    destination = ENVS / name
    if destination.exists() and not args.replace:
        raise FileExistsError(f"Environment already exists: {destination}; use --replace after reviewing it")
    ENVS.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{name}.build-", dir=str(ENVS)))
    try:
        # Build beside target, then atomically activate. Never remove an existing env until staging succeeds.
        run([str(py), "-m", "venv", str(stage / "env")])
        envdir = stage / "env"
        envpy = envdir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run([str(envpy), "-m", "pip", "--version"])
        req = Path(args.requirements).expanduser().resolve() if args.requirements else None
        if req and not req.is_file(): raise FileNotFoundError(f"Requirements file not found: {req}")
        smoke = run([str(envpy), "-c", "import sys; assert sys.prefix != sys.base_prefix; print(sys.version)"])
        # Virtualenv launchers embed their creation path. After staging is moved into
        # its final location, repair the environment there and validate that final path.
        backup = None
        if destination.exists():
            if not args.replace:
                raise FileExistsError(f"Environment already exists: {destination}; use --replace after reviewing it")
            backup = ENVS / f".{name}.previous-{os.getpid()}"
            if backup.exists(): raise FileExistsError(f"Refusing to overwrite existing backup: {backup}")
            os.replace(destination, backup)
        activated = False
        try:
            os.replace(envdir, destination)
            activated = True
            final_py = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            run([str(final_py), "-m", "venv", "--upgrade", str(destination)])
            if req:
                run([str(final_py), "-m", "pip", "install", "-r", str(req)])
            final_info = json.loads(run([str(final_py), "-c", "import json,sys; print(json.dumps({'prefix':sys.prefix,'base_prefix':sys.base_prefix,'executable':sys.executable}))"]).stdout.strip().splitlines()[-1])
            if Path(final_info["prefix"]).resolve() != destination.resolve() or Path(final_info["prefix"]).resolve() == Path(final_info["base_prefix"]).resolve():
                raise RuntimeError(f"Final environment isolation/path validation failed: {final_info}")
            manifest = load_manifest()
            old_app = manifest.get("applications", {}).get(name, {})
            manifest.setdefault("applications", {})[name] = {"environment_relative_path": destination.relative_to(STATE_ROOT).as_posix(), "platform": platform_key(), "python_version": info["version"], "requirements_file": req.name if req else None, "created_by_manager": VERSION, "environment_executable": final_info["executable"], "isolation_verified": True}
            try:
                atomic_json(MANIFEST, manifest)
            except Exception:
                # Restore the previous manifest state if the atomic write fails.
                raise
        except Exception:
            if activated and destination.exists(): shutil.rmtree(destination, ignore_errors=True)
            if backup and backup.exists(): os.replace(backup, destination)
            raise
        if backup:
            print(f"previous_environment_preserved_at: {backup}")
        print(f"environment: {destination}")
        print(f"base_python: {py}")
        print(f"smoke: PASS ({smoke.stdout.strip().splitlines()[-1]})")
        print("final_path_validation: PASS")
        return 0
    finally:
        if stage.exists(): shutil.rmtree(stage, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--home", help="shared managed runtime home used by multiple applications; defaults to JULIAN_RUNTIME_HOME or project-local state")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="inspect managed runtime without changing files").set_defaults(func=cmd_doctor)
    sub.add_parser("register-runtime", help="register the already-staged compatible managed runtime").set_defaults(func=cmd_register)
    sub.add_parser("list", help="list managed runtimes and app environments").set_defaults(func=cmd_list)
    c = sub.add_parser("create-env", help="create an isolated environment for one app")
    c.add_argument("app_id")
    c.add_argument("--requirements", help="optional requirements.txt for this app")
    c.add_argument("--base-python", help="explicit interpreter for controlled bootstrap/build; production should omit")
    c.add_argument("--replace", action="store_true", help="stage new env then preserve prior env under a backup name")
    c.set_defaults(func=cmd_create)
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        configure_home(args.home)
        return args.func(args)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"[RUNTIME MANAGER ERROR] {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError): print(exc.stdout, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
