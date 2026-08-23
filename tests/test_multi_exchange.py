from datetime import datetime, timezone
from decimal import Decimal

from abdalghoniy.analytics import DailyCandle, calendar_range, period_ranges
from abdalghoniy.multi_exchange import ExchangeBudget, SourceRouter, normalise_bybit_kline


def candle(day, high, low, close=None):
    close = close or high
    return DailyCandle(datetime.fromisoformat(day).replace(tzinfo=timezone.utc), close, max(high, close), min(low, close), close, 1)


def test_calendar_range_supports_year_and_explicit_period():
    result = calendar_range([candle("2025-12-31", 10, 8), candle("2026-01-02", 12, 7)], "year")
    assert result.available is True
    assert result.value.start.isoformat() == "2026-01-01"
    assert result.value.end.isoformat() == "2026-12-31"
    assert result.value.high == Decimal("12")
    assert result.value.low == Decimal("7")


def test_exchange_budget_denies_until_next_interval_without_sleeping():
    budget = ExchangeBudget(max_requests=1, window_ms=1000, clock_ms=lambda: 1000)
    assert budget.allow() is True
    assert budget.allow() is False


def test_router_uses_fallback_only_after_primary_failure():
    calls = []
    router = SourceRouter([("primary", lambda: calls.append("primary") or (_ for _ in ()).throw(RuntimeError("down"))), ("fallback", lambda: calls.append("fallback") or "ok")])
    assert router.fetch() == ("fallback", "ok")
    assert calls == ["primary", "fallback"]


def test_bybit_kline_is_normalised_to_daily_candle_rows():
    rows = normalise_bybit_kline({"result": {"list": [["1760000000000", "100", "110", "90", "105", "3", "315"]]}})
    assert rows[0][0] == "1760000000000"
    assert rows[0][2] == "110"
    assert rows[0][5] == "3"
