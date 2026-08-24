from abdalghoniy.dashboard import intelligence_snapshot


def test_intelligence_snapshot_has_explicit_panels_and_unavailable_liquidations(monkeypatch):
    class FakeClient:
        def candles(self, symbol, *, granularity, limit):
            rows = []
            for i in range(40):
                ts = str(1760000000000 + i * 86400000)
                close = str(100 + i % 5)
                rows.append([ts, "99", str(101 + i % 5), "98", close, "10"])
            return type("R", (), {"data": rows, "metadata": type("M", (), {"source": "Bitget", "method": "GET", "updated_at_ms": int(rows[-1][0]), "freshness_ms": 0, "stale": False, "rate_limit": {"limit": 20, "window": "1s"}})()})()

        def depth(self, symbol, *, limit):
            return type("R", (), {"data": {"bids": [["100", "2"]], "asks": [["101", "1"]], "ts": "1760000000000"}, "metadata": type("M", (), {"source": "Bitget", "method": "GET", "updated_at_ms": 1760000000000, "freshness_ms": 0, "stale": False, "rate_limit": {"limit": 20, "window": "1s"}})()})()

    monkeypatch.setattr("abdalghoniy.dashboard.PublicBitgetMarketData", lambda: FakeClient())
    payload = intelligence_snapshot()
    assert set(payload) >= {"ranges", "rsi", "support_resistance", "smc", "order_book", "liquidations", "freshness", "rate_limit"}
    assert payload["liquidations"]["status"] == "unavailable"
    assert payload["order_book"]["status"] == "ok"
    assert payload["freshness"]["freshness_ms"] is not None
    assert payload["freshness"]["kind"] == "historical_daily"
    assert payload["order_book_freshness"]["kind"] == "order_book"
