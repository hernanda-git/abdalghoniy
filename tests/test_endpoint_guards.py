from abdalghoniy.multi_exchange import EndpointGuard, GuardDecision


def test_endpoint_guard_is_scoped_per_endpoint_key():
    now = [1000]
    guard = EndpointGuard(max_requests=1, window_ms=1000, clock_ms=lambda: now[0])
    assert guard.check("bybit:/v5/market/kline").allowed
    assert not guard.check("bybit:/v5/market/kline").allowed
    assert guard.check("bybit:/v5/market/orderbook").allowed


def test_endpoint_guard_cooldown_blocks_after_rate_limit_error():
    now = [1000]
    guard = EndpointGuard(max_requests=5, window_ms=1000, cooldown_ms=5000, clock_ms=lambda: now[0])
    guard.record_error("hyperliquid:/info", "429")
    decision = guard.check("hyperliquid:/info")
    assert decision.allowed is False
    assert decision.reason == "cooldown"
    now[0] = 6000
    assert guard.check("hyperliquid:/info").allowed


def test_endpoint_guard_reports_remaining_budget():
    guard = EndpointGuard(max_requests=2, window_ms=1000, clock_ms=lambda: 1000)
    first = guard.check("mexc:/api/v1/contract/kline")
    assert isinstance(first, GuardDecision)
    assert first.remaining == 1
