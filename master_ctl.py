#!/usr/bin/env python3
import os, sys, sqlite3, signal, time, subprocess, urllib.request, socket, shutil
from pathlib import Path
from datetime import datetime, timezone
import uuid

SOURCE = Path(__file__).resolve().parent
DB_PATH = SOURCE / "system.db"

def now(): return datetime.now(timezone.utc).isoformat()

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            service_type TEXT NOT NULL,     -- 'app' or 'model'
            path TEXT NOT NULL,
            port INTEGER,
            pid INTEGER,
            status TEXT DEFAULT 'stopped',
            created_at TEXT,
            updated_at TEXT
        );
    """)
    con.commit()
    con.close()

def get_service(name):
    con = db()
    row = con.execute("SELECT * FROM services WHERE name=?", (name,)).fetchone()
    con.close()
    return dict(row) if row else None

def list_services(service_type=None):
    con = db()
    if service_type:
        rows = con.execute("SELECT * FROM services WHERE service_type=? ORDER BY name", (service_type,)).fetchall()
    else:
        rows = con.execute("SELECT * FROM services ORDER BY service_type, name").fetchall()
    con.close()
    return [dict(r) for r in rows]

def update_service(name, **kwargs):
    if not kwargs: return
    kwargs["updated_at"] = now()
    set_clause = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [name]
    con = db()
    con.execute(f"UPDATE services SET {set_clause} WHERE name=?", values)
    con.commit()
    con.close()

def is_pid_alive(pid):
    if not pid: return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def health_ok(url, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200: return True
        except Exception: pass
        time.sleep(1)
    return False

def find_gguf(path_str):
    p = SOURCE / path_str
    if p.exists() and p.suffix == ".gguf": return p
    model_dir = p.parent if p.parent.exists() else SOURCE / "models" / "primary"
    for f in sorted(model_dir.glob("*.gguf")):
        return f
    return None

def start_service(svc):
    name = svc["name"]
    if is_pid_alive(svc["pid"]):
        print(f"  ⏭️  {name}: already running (PID {svc['pid']})")
        return True
    if is_port_in_use(svc["port"]):
        print(f"  ⚠️  {name}: port {svc['port']} already in use.")
        return False

    update_service(name, status="starting")
    log_dir = SOURCE / "logs" / "services"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"

    if svc["service_type"] == "model":
        gguf = find_gguf(svc["path"])
        if not gguf: return False
        cmd = [str(SOURCE / "runtimes/llama.cpp/macos-arm64/llama-server"),
               "-m", str(gguf), "--host", "127.0.0.1", "--port", str(svc["port"]),
               "-c", "8192", "-ngl", "99", "--threads", "-1"]
        health_url = f"http://127.0.0.1:{svc['port']}/v1/models"
    else:
        venv_py = SOURCE / "environments" / name / "bin" / "python"
        if not venv_py.exists():
            print(f"  ❌ {name}: venv missing.")
            return False
        cmd = [str(venv_py), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(svc["port"])]
        health_url = f"http://127.0.0.1:{svc['port']}/api/health"

    with open(log_path, "ab") as logf:
        proc = subprocess.Popen(cmd, cwd=str(SOURCE / (svc["path"] if svc["service_type"] == "app" else "runtimes/llama.cpp/macos-arm64")),
                                stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    update_service(name, pid=proc.pid)
    print(f"  ⏳ {name}: waiting for health...")
    if health_ok(health_url, 60):
        update_service(name, status="running")
        print(f"  ✅ {name}: running (PID {proc.pid}, port {svc['port']})")
        return True
    else:
        print(f"  ❌ {name}: failed health check. See {log_path}")
        update_service(name, status="crashed")
        return False

def stop_service(svc):
    pid = svc["pid"]
    if not is_pid_alive(pid):
        update_service(svc["name"], status="stopped", pid=None)
        return
    print(f"  ⏹️  {svc['name']}: stopping...")
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(10):
            time.sleep(0.5)
            if not is_pid_alive(pid): break
        else: os.kill(pid, signal.SIGKILL)
    except ProcessLookupError: pass
    update_service(svc["name"], status="stopped", pid=None)

# ===== COMMANDS =====

def cmd_start(targets):
    init_db()
    models = list_services("model")
    
    # 1. Always start models first
    if models:
        print("\n[Starting Models]")
        for svc in models:
            start_service(svc)
    
    # 2. Start apps
    apps = list_services("app")
    if targets:
        # Filter apps based on user input
        apps_to_start = [a for a in apps if a["name"] in targets]
        missing = set(targets) - set([a["name"] for a in apps_to_start])
        if missing:
            print(f"⚠️  Unknown app names: {missing}")
    else:
        apps_to_start = apps

    if apps_to_start:
        print(f"\n[Starting Apps]")
        for svc in apps_to_start:
            start_service(svc)

def cmd_stop():
    init_db()
    print("⏹️  Stopping all services...")
    for svc in list_services("app") + list_services("model"):
        stop_service(svc)
    print("✅ All stopped.")

def cmd_status():
    init_db()
    services = list_services()
    print(f"{'NAME':<20} {'TYPE':<8} {'STATUS':<10} {'PORT':<6} {'PID':<8}")
    print("-" * 60)
    for s in services:
        alive = " (alive)" if is_pid_alive(s["pid"]) else ""
        print(f"{s['name']:<20} {s['service_type']:<8} {s['status']:<10} {s['port'] or '-':<6} {(s['pid'] or '-')}{alive}")

def cmd_add_app(name, app_path):
    init_db()
    if get_service(name):
        print(f"❌ '{name}' already exists."); return
    app_dir = SOURCE / app_path
    if not (app_dir / "requirements.txt").exists():
        print(f"❌ No requirements.txt in {app_dir}"); return
    
    # Auto-assign port (starts at 8080, increments by 10)
    used_ports = [s["port"] for s in list_services("app") if s["port"]]
    port = 8080
    while port in used_ports: port += 10
    
    print(f"🔧 Creating venv for '{name}' (Port: {port})...")
    base_py = SOURCE / "runtimes" / "python" / "macos-arm64" / "python313" / "bin" / "python3.13"
    venv_dir = SOURCE / "environments" / name
    subprocess.run([str(base_py), "-m", "venv", str(venv_dir)], check=True)
    subprocess.run([str(venv_dir / "bin" / "pip"), "install", "-q", "--upgrade", "pip"], check=True)
    subprocess.run([str(venv_dir / "bin" / "pip"), "install", "-q", "-r", str(app_dir / "requirements.txt")], check=True)

    con = db()
    con.execute("INSERT INTO services(id,name,service_type,path,port,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), name, "app", app_path, port, "stopped", now(), now()))
    con.commit(); con.close()
    print(f"✅ Registered '{name}' on port {port}.")

def cmd_add_model(name, model_path):
    init_db()
    if get_service(name):
        print(f"❌ '{name}' already exists."); return
    
    # Auto-assign port (starts at 8081)
    used_ports = [s["port"] for s in list_services("model") if s["port"]]
    port = 8081
    while port in used_ports: port += 1
    
    con = db()
    con.execute("INSERT INTO services(id,name,service_type,path,port,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), name, "model", model_path, port, "stopped", now(), now()))
    con.commit(); con.close()
    print(f"✅ Registered model '{name}' on port {port}.")

def cmd_remove(name):
    init_db()
    svc = get_service(name)
    if not svc:
        print(f"❌ '{name}' not found."); return
    stop_service(svc)
    if svc["service_type"] == "app":
        venv_dir = SOURCE / "environments" / name
        if venv_dir.exists(): shutil.rmtree(venv_dir)
    con = db()
    con.execute("DELETE FROM services WHERE name=?", (name,))
    con.commit(); con.close()
    print(f"✅ Removed '{name}'.")

def main():
    args = sys.argv[1:]
    if not args: print("Usage: master_add-remove.sh [add-app|add-model|remove|status]"); return
    cmd = args[0]
    
    if cmd == "start":
        cmd_start(args[1:])
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "status":
        cmd_status()
    elif cmd == "add-app" and len(args) >= 3:
        cmd_add_app(args[1], args[2])
    elif cmd == "add-model" and len(args) >= 3:
        cmd_add_model(args[1], args[2])
    elif cmd == "remove" and len(args) >= 2:
        cmd_remove(args[1])
    else:
        print("Commands: start, stop, status, add-app <name> <path>, add-model <name> <path>, remove <name>")

if __name__ == "__main__":
    main()
