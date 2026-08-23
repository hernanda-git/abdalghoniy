from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from abdalghoniy.analytics import (
    DailyCandle,
    period_ranges,
    pivot_clusters,
    rsi,
    smc_events,
)


def candle(day, open_, high, low, close, volume=1):
    return DailyCandle(day, open_, max(high, open_, close), min(low, open_, close), close, volume)


def test_week_ranges_use_monday_to_sunday_calendar_and_real_candles_only():
    candles = [
        candle("2026-01-02", 10, 12, 9, 11, 2),  # Friday
        candle("2026-01-05", 11, 14, 10, 13, 3),  # Monday
        candle("2026-01-07", 13, 15, 12, 14, 4),
    ]

    ranges = period_ranges(candles, "week")

    assert [(item.start, item.end, item.candle_count) for item in ranges] == [
        (date(2025, 12, 29), date(2026, 1, 4), 1),
        (date(2026, 1, 5), date(2026, 1, 11), 2),
    ]
    assert ranges[1].open == Decimal("11")
    assert ranges[1].high == Decimal("15")
    assert ranges[1].low == Decimal("10")
    assert ranges[1].close == Decimal("14")
    assert ranges[1].volume == Decimal("7")


def test_month_ranges_use_first_to_last_calendar_day():
    candles = [candle("2026-02-27", 10, 11, 9, 10), candle("2026-03-01", 10, 13, 8, 12)]

    ranges = period_ranges(candles, "month")

    assert [(item.start, item.end) for item in ranges] == [
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 31)),
    ]


def test_period_ranges_reject_unsupported_period():
    with pytest.raises(ValueError, match="period must be 'week' or 'month'"):
        period_ranges([candle("2026-01-01", 1, 1, 1, 1)], "quarter")


def test_rsi_returns_wilder_value_from_real_closes():
    candles = [candle(f"2026-01-{day:02d}", 1, 1, 1, close) for day, close in enumerate([1, 2, 3, 2, 2, 4], 1)]

    result = rsi(candles, period=3)

    assert result.available is True
    assert result.value == Decimal("86.67")
    assert result.reason is None


def test_rsi_is_explicitly_unavailable_without_period_plus_one_closes():
    result = rsi([candle("2026-01-01", 1, 1, 1, 1), candle("2026-01-02", 1, 1, 1, 2)], period=3)

    assert result.available is False
    assert result.value is None
    assert "at least 4" in result.reason


def test_pivot_clusters_group_nearby_confirmed_swing_levels():
    candles = [
        candle(f"2026-01-{day:02d}", 10, high, low, 10)
        for day, high, low in [
            (1, 11, 9), (2, 13, 10), (3, 12, 10), (4, 11, 8),
            (5, 10, 9), (6, 11, 8), (7, 14, 11),
        ]
    ]

    result = pivot_clusters(candles, left=1, right=1, tolerance=Decimal("0.02"))

    assert result.available is True
    assert [(level.kind, level.price, level.touches) for level in result.value] == [
        ("resistance", Decimal("13"), 1),
        ("support", Decimal("8"), 2),
    ]


def test_smc_events_explain_break_of_confirmed_structure():
    candles = [
        candle(f"2026-01-{day:02d}", open_, high, low, close)
        for day, open_, high, low, close in [
            (1, 10, 11, 9, 10), (2, 10, 13, 10, 12), (3, 12, 12, 10, 11),
            (4, 11, 12, 8, 9), (5, 9, 11, 8, 10), (6, 10, 15, 9, 14),
        ]
    ]

    result = smc_events(candles, left=1, right=1)

    assert result.available is True
    assert [(event.kind, event.index) for event in result.value] == [("BOS_BULLISH", 5)]
    assert "closed above" in result.value[0].explanation
    assert "swing high" in result.value[0].explanation


def test_smc_events_are_unavailable_when_structure_cannot_be_confirmed():
    result = smc_events([candle("2026-01-01", 1, 2, 1, 1)], left=2, right=2)

    assert result.available is False
    assert result.value == []
    assert "at least 5" in result.reason
