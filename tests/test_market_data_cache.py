import time

from abdalghoniy.market_data import MarketDataCache, MarketDataScheduler, PublicBitgetMarketData


def test_public_client_returns_structured_ticker_metadata_and_demo_endpoint():
    calls = []

    def transport(method, url, headers=None, body=None):
        calls.append((method, url, headers, body))
        return {"code": "00000", "data": [{"symbol": "SBTCSUSDT", "lastPr": "100.5", "markPrice": "100.4", "ts": "1700000000000"}]}

    client = PublicBitgetMarketData(transport=transport, clock_ms=lambda: 1700000060000)
    result = client.ticker("BTCUSDT")

    assert result.data["lastPr"] == "100.5"
    assert result.metadata.source == "Bitget"
    assert result.metadata.method == "GET /api/v2/mix/market/ticker"
    assert result.metadata.updated_at_ms == 1700000000000
    assert result.metadata.freshness_ms == 60000
    assert result.metadata.stale is False
    assert result.metadata.rate_limit["limit"] == 20
    assert "productType=SUSDT-FUTURES" in calls[0][1]
    assert "symbol=SBTCSUSDT" in calls[0][1]
    assert calls[0][0] == "GET"
    assert calls[0][2] == {}


def test_cache_serves_fresh_value_without_second_network_call():
    calls = []

    def fetcher():
        calls.append(1)
        return {"value": len(calls)}

    cache = MarketDataCache(clock_ms=lambda: 1000)
    first = cache.get_or_fetch("ticker:BTCUSDT", fetcher, ttl_ms=5000)
    second = cache.get_or_fetch("ticker:BTCUSDT", fetcher, ttl_ms=5000)

    assert first == second == {"value": 1}
    assert calls == [1]


def test_scheduler_only_runs_due_jobs_and_exposes_last_result():
    now = [1000]
    calls = []
    scheduler = MarketDataScheduler(clock_ms=lambda: now[0])
    scheduler.register("ticker", lambda: calls.append(now[0]) or now[0], interval_ms=1000)

    assert scheduler.run_due() == {"ticker": 1000}
    assert scheduler.run_due() == {}
    now[0] = 2000
    assert scheduler.run_due() == {"ticker": 2000}
    assert scheduler.last_results["ticker"] == 2000
    assert calls == [1000, 2000]


def test_public_client_marks_unavailable_with_error_metadata():
    def transport(method, url, headers=None, body=None):
        raise TimeoutError("venue timeout")

    result = PublicBitgetMarketData(transport=transport).depth("BTCUSDT")

    assert result.data is None
    assert result.metadata.unavailable is True
    assert result.metadata.stale is True
    assert result.metadata.error == "TimeoutError"
    assert result.metadata.method == "GET /api/v2/mix/market/orderbook"
