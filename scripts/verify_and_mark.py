#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

root = pathlib.Path(__file__).resolve().parents[1]
marker = root / '.dashboard_test_status'

def run(command):
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    return {"returncode": result.returncode, "output_tail": (result.stdout + result.stderr)[-2000:]}

checks = {
    "pytest": run([sys.executable, '-m', 'pytest', '-q']),
    "compileall": run([sys.executable, '-m', 'compileall', '-q', '.']),
    "frontend_build": run(['npm', 'run', 'build']),
}

endpoint = {"returncode": 1, "output_tail": "not checked"}
try:
    with urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=10) as response:
        payload = json.loads(response.read())
    safe = payload == {"status": "ok", "mode": "paper", "data_plane": "rest"}
    endpoint = {"returncode": 0 if safe else 1, "output_tail": json.dumps(payload)}
except Exception as exc:
    endpoint = {"returncode": 1, "output_tail": f"{type(exc).__name__}: {exc}"}
checks["endpoint_smoke"] = endpoint

commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True).stdout.strip()
passed = all(item["returncode"] == 0 for item in checks.values())
marker.write_text(json.dumps({
    "status": "passing" if passed else "failing",
    "evaluated_at": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
    "commit": commit,
    "checks": checks,
}, indent=2) + "\n")
sys.exit(0 if passed else 1)
