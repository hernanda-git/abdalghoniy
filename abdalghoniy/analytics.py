"""Deterministic, read-only market analytics over timestamped daily candles.

This module deliberately produces observations, not trading signals or orders. Every
result reports whether the input contains enough data for the requested calculation.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class DailyCandle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __init__(self, timestamp, open, high, low, close, volume):
        object.__setattr__(self, "timestamp", _as_datetime(timestamp))
        values = {"open": open, "high": high, "low": low, "close": close, "volume": volume}
        for name, value in values.items():
            object.__setattr__(self, name, Decimal(str(value)))
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("candle high/low must contain open and close")
        if self.volume < 0:
            raise ValueError("candle volume cannot be negative")


@dataclass(frozen=True)
class AnalysisResult(Generic[T]):
    value: T
    available: bool
    reason: str | None = None


@dataclass(frozen=True)
class PeriodRange:
    start: date
    end: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    candle_count: int


@dataclass(frozen=True)
class PivotLevel:
    kind: str
    price: Decimal
    touches: int
    source_indices: tuple[int, ...]


@dataclass(frozen=True)
class SMCEvent:
    kind: str
    index: int
    price: Decimal
    explanation: str


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str):
        text = value.replace("Z", "+00:00")
        result = datetime.fromisoformat(text)
    else:
        raise TypeError("timestamp must be a date, datetime, or ISO-8601 string")
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _ordered(candles: Sequence[DailyCandle]) -> list[DailyCandle]:
    result = list(candles)
    if any(not isinstance(item, DailyCandle) for item in result):
        raise TypeError("candles must contain DailyCandle values")
    return sorted(result, key=lambda item: item.timestamp)


def period_ranges(candles: Sequence[DailyCandle], period: str) -> list[PeriodRange]:
    """Aggregate observed candles into calendar weeks or calendar months.

    Weeks are Monday through Sunday. Months are the first through last calendar day.
    Missing days remain missing and do not get synthesized into the OHLCV values.
    """
    if period not in {"week", "month"}:
        raise ValueError("period must be 'week' or 'month'")
    groups: dict[tuple[int, int], list[DailyCandle]] = {}
    for candle in _ordered(candles):
        day = candle.timestamp.date()
        key = day.isocalendar()[:2] if period == "week" else (day.year, day.month)
        groups.setdefault(key, []).append(candle)
    output: list[PeriodRange] = []
    for rows in groups.values():
        first, last = rows[0].timestamp.date(), rows[-1].timestamp.date()
        if period == "week":
            start = first.fromordinal(first.toordinal() - first.weekday())
            end = date.fromordinal(start.toordinal() + 6)
        else:
            start = date(first.year, first.month, 1)
            end = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
        output.append(PeriodRange(start, end, rows[0].open, max(x.high for x in rows), min(x.low for x in rows), rows[-1].close, sum((x.volume for x in rows), Decimal("0")), len(rows)))
    return output


def rsi(candles: Sequence[DailyCandle], period: int = 14) -> AnalysisResult[Decimal | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    rows = _ordered(candles)
    if len(rows) < period + 1:
        return AnalysisResult(None, False, f"RSI requires at least {period + 1} candles")
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for previous, current in zip(rows, rows[1:]):
        change = current.close - previous.close
        gains.append(max(change, Decimal("0")))
        losses.append(max(-change, Decimal("0")))
    average_gain = sum(gains[:period], Decimal("0")) / period
    average_loss = sum(losses[:period], Decimal("0")) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
    if average_loss == 0:
        value = Decimal("100") if average_gain else Decimal("50")
    else:
        value = Decimal("100") - (Decimal("100") / (Decimal("1") + average_gain / average_loss))
    return AnalysisResult(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), True)


def _pivots(candles: Sequence[DailyCandle], left: int, right: int) -> tuple[list[tuple[int, Decimal]], list[tuple[int, Decimal]]]:
    rows = _ordered(candles)
    highs, lows = [], []
    for index in range(left, len(rows) - right):
        window = rows[index - left:index + right + 1]
        if rows[index].high == max(item.high for item in window) and rows[index].high > max((item.high for item in window[:left]), default=Decimal("-Infinity")) and rows[index].high > max((item.high for item in window[left + 1:]), default=Decimal("-Infinity")):
            highs.append((index, rows[index].high))
        if rows[index].low == min(item.low for item in window) and rows[index].low < min((item.low for item in window[:left]), default=Decimal("Infinity")) and rows[index].low < min((item.low for item in window[left + 1:]), default=Decimal("Infinity")):
            lows.append((index, rows[index].low))
    return highs, lows


def pivot_clusters(candles: Sequence[DailyCandle], left: int = 2, right: int = 2, tolerance: Decimal = Decimal("0.005")) -> AnalysisResult[list[PivotLevel]]:
    if left < 1 or right < 1 or tolerance < 0:
        raise ValueError("left, right, and tolerance must be valid positive values")
    rows = _ordered(candles)
    if len(rows) < left + right + 1:
        return AnalysisResult([], False, f"pivot detection requires at least {left + right + 1} candles")
    highs, lows = _pivots(rows, left, right)
    clusters: list[PivotLevel] = []
    for kind, points in (("resistance", highs), ("support", lows)):
        for index, price in points:
            match = next((i for i, level in enumerate(clusters) if level.kind == kind and abs(price - level.price) <= max(price, level.price) * tolerance), None)
            if match is None:
                clusters.append(PivotLevel(kind, price, 1, (index,)))
            else:
                old = clusters[match]
                new_price = (old.price * old.touches + price) / (old.touches + 1)
                clusters[match] = PivotLevel(kind, new_price, old.touches + 1, old.source_indices + (index,))
    clusters.sort(key=lambda level: (0 if level.kind == "resistance" else 1, -level.price))
    if not clusters:
        return AnalysisResult([], False, "no confirmed swing pivots in the supplied candles")
    return AnalysisResult(clusters, True)


def smc_events(candles: Sequence[DailyCandle], left: int = 2, right: int = 2) -> AnalysisResult[list[SMCEvent]]:
    if left < 1 or right < 1:
        raise ValueError("left and right must be positive")
    rows = _ordered(candles)
    minimum = left + right + 1
    if len(rows) < minimum:
        return AnalysisResult([], False, f"SMC structure requires at least {minimum} candles")
    highs, lows = _pivots(rows, left, right)
    events: list[SMCEvent] = []
    last_break: str | None = None
    for index, candle in enumerate(rows):
        prior_high = next(((pivot_index, price) for pivot_index, price in reversed(highs) if pivot_index < index), None)
        prior_low = next(((pivot_index, price) for pivot_index, price in reversed(lows) if pivot_index < index), None)
        direction = None
        pivot_index, level = prior_high or (None, None)
        if pivot_index is not None and candle.close > level:
            direction = "bullish"
            kind = "BOS_BULLISH" if last_break in {None, "bullish"} else "CHOCH_BULLISH"
            events.append(SMCEvent(kind, index, candle.close, f"Candle {index} closed above confirmed swing high {level} at candle {pivot_index}."))
        pivot_index, level = prior_low or (None, None)
        if pivot_index is not None and candle.close < level:
            direction = "bearish"
            kind = "BOS_BEARISH" if last_break in {None, "bearish"} else "CHOCH_BEARISH"
            events.append(SMCEvent(kind, index, candle.close, f"Candle {index} closed below confirmed swing low {level} at candle {pivot_index}."))
        if direction is not None:
            last_break = direction
    if not events:
        return AnalysisResult([], False, "no confirmed structure break in the supplied candles")
    return AnalysisResult(events, True)
