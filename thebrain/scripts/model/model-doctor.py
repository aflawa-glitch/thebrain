#!/usr/bin/env python3
"""Read-only local Qwen/llama.cpp integration preflight."""
from __future__ import annotations
import os, platform, urllib.request, json
from pathlib import Path

def key() -> str:
    os_name = {'Darwin':'macos','Windows':'windows','Linux':'linux'}.get(platform.system(), platform.system().lower())
    arch = {'AMD64':'x86_64','x64':'x86_64','aarch64':'arm64','ARM64':'arm64'}.get(platform.machine(), platform.machine().lower())
    return f'{os_name}-{arch}'

root = Path(__file__).resolve().parents[2]
config = root / 'config' / 'local-model.env'
print('Julian local model integration doctor (read-only)')
print(f'project_root: {root}')
print(f'platform: {key()}')
print(f'config_exists: {config.exists()}')
print('Note: shell env file is not evaluated here; paths are verified by start-model.sh.')
base = os.environ.get('JULIAN_LLM_BASE_URL', 'http://127.0.0.1:8081/v1').rstrip('/')
try:
    with urllib.request.urlopen(base + '/models', timeout=3) as response:
        body = json.loads(response.read().decode('utf-8'))
    print(f'model_endpoint: reachable ({base}/models)')
    print(f'models: {[x.get("id") for x in body.get("data", [])]}')
except Exception as exc:
    print(f'model_endpoint: unavailable ({type(exc).__name__}: {exc})')
    print('This is a live endpoint check, not a proof that inference succeeds.')
