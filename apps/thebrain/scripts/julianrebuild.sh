#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
usage() {
  cat <<'USAGE'
TheBrain / Julian — rebuild and maintenance entry point

Usage:
  ./julianrebuild.sh install
  ./julianrebuild.sh check
  ./julianrebuild.sh test
  ./julianrebuild.sh run
  ./julianrebuild.sh preflight
  ./julianrebuild.sh backup <destination-directory>
  ./julianrebuild.sh restore <backup-file> <absolute-database-path>
  JULIAN_DEPLOY_CONFIRM=YES JULIAN_RUNTIME_STOPPED=YES ./julianrebuild.sh deploy <absolute-target-directory>

Environment:
  JULIAN_HOST, JULIAN_PORT, JULIAN_DATA_DIR, JULIAN_DATABASE_PATH
  JULIAN_LLM_BASE_URL, JULIAN_LLM_MODEL, JULIAN_LLM_API_KEY
  JULIAN_LLM_ENABLED, JULIAN_WEB_SEARCH_ENABLED

The script never guesses an external runtime path or overwrites a database automatically.
USAGE
}
cd "$ROOT"
command="${1:-help}"
case "$command" in
  install)
    "$PYTHON_BIN" -m pip install -r requirements.txt
    ;;
  check)
    "$PYTHON_BIN" -m compileall -q app tests main.py
    bash -n scripts/julianrebuild.sh
    [[ ! -f scripts/deploy_safe.sh ]] || bash -n scripts/deploy_safe.sh
    if command -v node >/dev/null 2>&1; then node --check app/static/app.js; else echo "SKIP: node unavailable; JavaScript syntax check not run."; fi
    echo "PASS: source syntax checks completed."
    ;;
  test)
    "$PYTHON_BIN" -m pytest -q
    ;;
  run)
    exec "$PYTHON_BIN" -m uvicorn app.main:app --host "${JULIAN_HOST:-127.0.0.1}" --port "${JULIAN_PORT:-8080}"
    ;;
  preflight)
    "$PYTHON_BIN" - <<'PREFLIGHT'
from app.core.config import settings
from app.core.database import preflight_database_path
result = preflight_database_path()
print("Read-only Julian runtime preflight")
print(f"Data directory: {settings.resolved_data_dir}")
print(f"Database path: {result['database_path']}")
print(f"Database exists: {result['database_exists']}")
print(f"Database parent exists: {result['database_parent_exists']}")
print(f"Nearest existing parent: {result['nearest_existing_parent']}")
print(f"Nearest existing parent writable: {result['nearest_existing_parent_writable']}")
print(f"Status: {result['status']}")
print("No database migration or write was performed.")
PREFLIGHT
    ;;
  backup)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    destination="$2"
    mkdir -p "$destination"
    db_path="$("$PYTHON_BIN" - <<'DBPATH'
from app.core.database import discover_database_path
print(discover_database_path())
DBPATH
)"
    if [[ ! -f "$db_path" ]]; then echo "BLOCKED: configured database does not exist: $db_path" >&2; exit 3; fi
    stamp="$(date +%Y%m%d_%H%M%S)"
    backup_path="$destination/julian_database_${stamp}.sqlite3"
    "$PYTHON_BIN" - "$db_path" "$backup_path" <<'BACKUPDB'
import sqlite3,sys
source,destination=sys.argv[1:]
with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
    src.backup(dst)
    result=dst.execute('PRAGMA integrity_check').fetchone()[0]
if result != 'ok': raise SystemExit('FAIL: backup integrity check: '+str(result))
print('PASS: SQLite online backup completed and passed integrity check.')
BACKUPDB
    shasum -a 256 "$backup_path" 2>/dev/null || sha256sum "$backup_path"
    echo "PASS: database backup created. No source files changed."
    ;;
  restore)
    [[ $# -eq 3 ]] || { usage; exit 2; }
    backup_file="$2"; target_db="$3"
    [[ -f "$backup_file" ]] || { echo "BLOCKED: backup file not found." >&2; exit 3; }
    [[ -n "$target_db" && "$target_db" = /* ]] || { echo "BLOCKED: provide an explicit absolute database path." >&2; exit 3; }
    "$PYTHON_BIN" - "$backup_file" <<'VALIDATEBACKUP'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as con:
    result=con.execute('PRAGMA integrity_check').fetchone()[0]
if result != 'ok': raise SystemExit('BLOCKED: backup database failed integrity check: '+str(result))
print('PASS: backup database integrity verified before restore.')
VALIDATEBACKUP
    echo "Restore will replace this database: $target_db"
    read -r -p "Type RESTORE to continue: " confirm
    [[ "$confirm" == "RESTORE" ]] || { echo "Cancelled."; exit 4; }
    mkdir -p "$(dirname "$target_db")"
    pre_restore=""
    if [[ -e "$target_db" ]]; then
      pre_restore="${target_db}.pre_restore.$(date +%Y%m%d_%H%M%S)"
      "$PYTHON_BIN" - "$target_db" "$pre_restore" <<'BACKUPTARGET'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as src, sqlite3.connect(sys.argv[2]) as dst:
    src.backup(dst)
    result=dst.execute('PRAGMA integrity_check').fetchone()[0]
if result != 'ok': raise SystemExit('BLOCKED: current target backup failed integrity check: '+str(result))
BACKUPTARGET
    fi
    cp -p "$backup_file" "$target_db"
    if ! "$PYTHON_BIN" - "$target_db" <<'CHECKRESTORE'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as con:
    result=con.execute('PRAGMA integrity_check').fetchone()[0]
if result != 'ok': raise SystemExit('FAIL: restored database integrity check: '+str(result))
print('PASS: restored database passes SQLite integrity check.')
CHECKRESTORE
    then
      if [[ -n "$pre_restore" && -f "$pre_restore" ]]; then cp -p "$pre_restore" "$target_db"; else rm -f "$target_db"; fi
      echo "FAIL: restore was rolled back after integrity check failure." >&2
      exit 5
    fi
    ;;
  deploy)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    [[ "${JULIAN_DEPLOY_CONFIRM:-}" == "YES" ]] || { echo "BLOCKED: set JULIAN_DEPLOY_CONFIRM=YES after reviewing the target and backup plan." >&2; exit 3; }
    [[ "${JULIAN_RUNTIME_STOPPED:-}" == "YES" ]] || { echo "BLOCKED: stop the target runtime and set JULIAN_RUNTIME_STOPPED=YES before deployment." >&2; exit 3; }
    target="$2"
    [[ "$target" = /* ]] || { echo "BLOCKED: deploy target must be an explicit absolute path." >&2; exit 3; }
    [[ "$target" != "$ROOT" && "$target" != "/" ]] || { echo "BLOCKED: refusing to deploy over repository root or filesystem root." >&2; exit 3; }
    exec "$ROOT/scripts/deploy_safe.sh" "$target"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $command" >&2; usage; exit 2
    ;;
esac
