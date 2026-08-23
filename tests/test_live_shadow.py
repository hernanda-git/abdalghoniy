import json

from abdalghoniy.live_shadow import LiveDemoShadow


def test_live_demo_shadow_polls_public_candles_without_orders(tmp_path):
    calls = []

    def fetcher(symbol, interval, limit):
        calls.append((symbol, interval, limit))
        return [["1700000000000", "100", "101", "99", "100.5", "2", "201"]]

    runner = LiveDemoShadow("BTCUSDT", event_path=tmp_path / "events.jsonl", fetcher=fetcher, now_ms=lambda: 1700000060000)
    result = runner.poll_once()
    assert result["symbol"] == "BTCUSDT"
    assert result["venue_symbol"] == "SBTCSUSDT"
    assert result["would_order"] is False
    assert result["cvd_change"] is None
    assert calls == [("SBTCSUSDT", "1m", 2)]
    assert json.loads((tmp_path / "events.jsonl").read_text().splitlines()[0])["raw"]


def test_live_demo_shadow_deduplicates_candles(tmp_path):
    row = ["1700000000000", "100", "101", "99", "100.5", "2", "201"]
    runner = LiveDemoShadow("BTCUSDT", event_path=tmp_path / "events.jsonl", fetcher=lambda *args: [row], now_ms=lambda: 1700000000000)
    assert runner.poll_once()["status"] == "ok"
    assert runner.poll_once()["status"] == "duplicate"
    assert len((tmp_path / "events.jsonl").read_text().splitlines()) == 2
