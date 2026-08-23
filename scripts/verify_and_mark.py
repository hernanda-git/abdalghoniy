#!/usr/bin/env python3
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[1]
result = subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=root)
marker = root / '.dashboard_test_status'
if result.returncode == 0:
    marker.write_text('passing\n')
else:
    marker.write_text('failing\n')
sys.exit(result.returncode)
