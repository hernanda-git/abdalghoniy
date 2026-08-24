from abdalghoniy.dashboard import build_freshness, refresh_freshness


def test_freshness_separates_source_age_from_request_age_and_applies_policy():
    payload = build_freshness(
        source_updated_at_ms=1_700_000_000_000,
        fetched_at_ms=1_700_000_060_000,
        now_ms=1_700_000_120_000,
        kind="historical_daily",
        source="Hyperliquid",
        stale_after_ms=86_400_000,
    )

    assert payload["source_age_ms"] == 120_000
    assert payload["request_age_ms"] == 60_000
    assert payload["freshness_ms"] == payload["source_age_ms"]
    assert payload["data_age_ms"] == payload["source_age_ms"]
    assert payload["stale"] is False
    assert payload["stale_policy"] == "source_age_ms > 86400000"
    assert payload["kind"] == "historical_daily"


def test_cached_freshness_recomputes_request_age_and_stale_state():
    cached = {
        "freshness": build_freshness(
            source_updated_at_ms=1_700_000_000_000,
            fetched_at_ms=1_700_000_000_000,
            now_ms=1_700_000_000_000,
            kind="historical_daily",
            source="Hyperliquid",
            stale_after_ms=86_400_000,
        ),
        "order_book_freshness": build_freshness(
            source_updated_at_ms=1_700_000_000_000,
            fetched_at_ms=1_700_000_000_000,
            now_ms=1_700_000_000_000,
            kind="order_book",
            source="Bitget",
            stale_after_ms=60_000,
        ),
    }

    refreshed = refresh_freshness(cached, 1_700_000_120_000)

    assert refreshed["freshness"]["request_age_ms"] == 120_000
    assert refreshed["freshness"]["source_age_ms"] == 120_000
    assert refreshed["freshness"]["stale"] is False
    assert refreshed["order_book_freshness"]["request_age_ms"] == 120_000
    assert refreshed["order_book_freshness"]["stale"] is True
    assert cached["freshness"]["request_age_ms"] == 0


def test_intelligence_snapshot_has_explicit_panels_and_unavailable_liquidations(monkeypatch):
    from abdalghoniy.dashboard import intelligence_snapshot
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
    assert payload["freshness"]["freshness_ms"] == payload["freshness"]["source_age_ms"]
    assert payload["freshness"]["kind"] == "historical_daily"
    assert payload["freshness"]["stale"] is (payload["freshness"]["source_age_ms"] > 172800000)
    assert payload["freshness"]["stale_policy"] == "source_age_ms > 172800000"
    assert payload["freshness"]["data_age_ms"] == payload["freshness"]["source_age_ms"]
    assert payload["rsi"]["period"] == 14
    assert payload["rsi"]["timeframe"] == "1D"
    assert payload["rsi"]["zone"] in {"overbought", "oversold", "neutral"}
    assert payload["smc"]["event_count"] == len(payload["smc"]["value"])
    assert len(payload["smc"]["recent_events"]) <= 8
    assert payload["smc"]["bias"] in {"bullish", "bearish", "unavailable"}
    assert payload["order_book_freshness"]["kind"] == "order_book"
