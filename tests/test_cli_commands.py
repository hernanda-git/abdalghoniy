import csv
import json
import subprocess
import sys
from pathlib import Path


def write_dataset(path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume", "cvd_change", "funding_bps"])
        writer.writeheader()
        writer.writerows([
            {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1, "cvd_change": 0, "funding_bps": 0},
            {"timestamp": "2026-01-01T00:01:00Z", "open": 100, "high": 102, "low": 100, "close": 102, "volume": 1, "cvd_change": -20, "funding_bps": 0},
            {"timestamp": "2026-01-01T00:02:00Z", "open": 102, "high": 102, "low": 98, "close": 99, "volume": 1, "cvd_change": 0, "funding_bps": 0},
        ])


def test_replay_and_report_commands(tmp_path):
    dataset = tmp_path / "candles.csv"
    write_dataset(dataset)
    replay = subprocess.run([
        sys.executable, "-m", "abdalghoniy", "replay", "--symbol", "BTCUSDT", "--interval", "1m",
        "--input", str(dataset), "--output-dir", str(tmp_path / "reports"),
    ], capture_output=True, text=True)
    assert replay.returncode == 0, replay.stderr
    payload = json.loads(replay.stdout)
    assert payload["symbol"] == "BTCUSDT"
    assert payload["trade_count"] == 1
    assert payload["dataset_hash"]
    report = subprocess.run([
        sys.executable, "-m", "abdalghoniy", "report", "--latest", "--output-dir", str(tmp_path / "reports"),
    ], capture_output=True, text=True)
    assert report.returncode == 0, report.stderr
    assert json.loads(report.stdout)["trade_count"] == 1
