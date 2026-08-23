from abdalghoniy.shadow import ShadowRunner


def test_shadow_runner_persists_events_and_never_calls_orders(tmp_path):
    calls = []
    runner = ShadowRunner(symbol="SBTCSUSDT", event_path=tmp_path / "events.jsonl", now=lambda: 115)
    result = runner.process({"timestamp": 100, "price": "100", "volume": "2"})
    assert result["status"] == "ok"
    assert result["would_order"] is False
    assert calls == []
    assert (tmp_path / "events.jsonl").read_text().count("\n") == 1


def test_shadow_runner_fails_closed_on_stale_and_gap():
    runner = ShadowRunner(symbol="SBTCSUSDT", max_age_s=10, max_gap_s=5, now=lambda: 120)
    assert runner.process({"timestamp": 100, "price": "100"})["status"] == "stale"
    runner = ShadowRunner(symbol="SBTCSUSDT", max_age_s=100, max_gap_s=5, now=lambda: 106)
    assert runner.process({"timestamp": 100, "price": "100"})["status"] == "ok"
    assert runner.process({"timestamp": 110, "price": "101"})["status"] == "gap"


def test_shadow_runner_uses_rest_fallback_after_stream_failure(tmp_path):
    runner = ShadowRunner(symbol="SBTCSUSDT", event_path=tmp_path / "events.jsonl", now=lambda: 100)
    result = runner.poll(lambda: (_ for _ in ()).throw(ConnectionError("stream down")), lambda: {"timestamp": 99, "price": "100"})
    assert result["source"] == "rest_fallback"
    assert result["status"] == "ok"
