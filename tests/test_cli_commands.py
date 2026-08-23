import csv
import json
import subprocess
import sys
from pathlib import Path

from abdalghoniy.data import fetch_demo_candles


def test_fetch_demo_candles_uses_demo_product_and_translates_symbol(monkeypatch, tmp_path):
    seen = {}

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"code":"00000","data":[["1700000000000","100","101","99","100.5","2","201"]]}'

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    output = fetch_demo_candles("BTCUSDT", "1m", output=tmp_path / "demo.csv")
    assert output.exists()
    assert "symbol=SBTCSUSDT" in seen["url"]
    assert "productType=SUSDT-FUTURES" in seen["url"]


def write_dataset(path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume", "cvd_change", "funding_bps"])
        writer.writeheader()
        writer.writerows([
            {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1, "cvd_change": 0, "funding_bps": 0},
            {"timestamp": "2026-01-01T00:01:00Z", "open": 100, "high": 102, "low": 100, "close": 102, "volume": 1, "cvd_change": -20, "funding_bps": 0},
            {"timestamp": "2026-01-01T00:02:00Z", "open": 102, "high": 102, "low": 98, "close": 99, "volume": 1, "cvd_change": 0, "funding_bps": 0},
        ])


def test_shadow_command_persists_zero_order_events(tmp_path):
    dataset = tmp_path / "candles.csv"
    write_dataset(dataset)
    result = subprocess.run([
        sys.executable, "-m", "abdalghoniy", "shadow", "--symbol", "BTCUSDT", "--input", str(dataset),
        "--event-path", str(tmp_path / "events.jsonl"),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["would_orders"] == 0
    assert payload["events"] == 3


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
