import subprocess
import sys


def test_paper_cli_help_and_status():
    help_result = subprocess.run([sys.executable, '-m', 'abdalghoniy', '--help'], capture_output=True, text=True)
    assert help_result.returncode == 0
    status_result = subprocess.run([sys.executable, '-m', 'abdalghoniy', '--status'], capture_output=True, text=True)
    assert status_result.returncode == 0
    assert 'paper' in status_result.stdout
