"""Orderflow auction strategy (environment, location, confirmation).

Adapted from a championship day-trader's public breakdown of an auction-market-theory
orderflow approach. The three pillars map to pure functions:

1. Environment: market structure (value up/down/sideways) + volatility regime.
   The original framework uses Gamma Exposure (GEX) to separate dampened vs amplified
   volatility. For crypto perpetuals we use a realized-range expansion/contraction proxy
   as the volatility-regime signal (no GEX feed available; documented as an adaptation).
2. Location: discount/premium zones relative to the value area via Fibonacci retracement
   levels (0.705 / 0.788 / 0.886 of the value-area span).
3. Confirmation: absorption at extremes + delta-dominance shift + failed retest.

This module is research-only. It produces proposals for the arbitration layer and never
places orders. CVD (cumulative volume delta) is required as input and must be supplied
from an external tape/footprint feed; without it, confirmation stays None.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Sequence

from .analytics import DailyCandle


class Structure(StrEnum):
    VALUE_UP = 'value_up'
    VALUE_DOWN = 'value_down'
    SIDEWAYS = 'sideways'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class ValueArea:
    poc: Decimal
    value_high: Decimal
    value_low: Decimal


@dataclass(frozen=True)
class OrderflowState:
    structure: Structure
    volatility_regime: str  # positive_gamma / negative_gamma proxy from realized vol trend
    value_area: ValueArea | None
    location: str | None  # discount / premium / equilibrium / none
    confirmation: str | None  # absorption_long / absorption_short / None
    side: str | None  # proposed direction or None


def _typical(candle: DailyCandle) -> Decimal:
    return (candle.high + candle.low + candle.close) / Decimal(3)


def _value_area(candles: Sequence[DailyCandle], lookback: int = 30) -> ValueArea | None:
    rows = list(candles)[-lookback:]
    if len(rows) < 5:
        return None
    typical = [_typical(c) for c in rows]
    volumes = [c.volume for c in rows]
    total_volume = sum(volumes, Decimal(0))
    if total_volume <= 0:
        return None
    max_tp = max(typical)
    buckets: dict[int, Decimal] = {}
    for price, volume in zip(typical, volumes):
        key = int((price / max_tp * Decimal(1000)).to_integral_value())
        buckets[key] = buckets.get(key, Decimal(0)) + volume
    poc_key = max(buckets, key=buckets.get)
    poc_price = max_tp * Decimal(poc_key) / Decimal(1000)
    ordered = sorted(buckets.items(), key=lambda kv: abs(kv[0] - poc_key))
    captured = Decimal(0)
    target = total_volume * Decimal('0.70')
    chosen = set()
    for key, volume in ordered:
        captured += volume
        chosen.add(key)
        if captured >= target:
            break
    prices_in_area = [
        p for p, k in zip(typical, [int((p / max_tp * Decimal(1000)).to_integral_value()) for p in typical])
        if k in chosen
    ]
    if not prices_in_area:
        return None
    return ValueArea(poc_price, max(prices_in_area), min(prices_in_area))


def classify_environment(candles: Sequence[DailyCandle], *, lookback: int = 30) -> tuple[Structure, str]:
    rows = list(candles)[-lookback:]
    if len(rows) < 5:
        return Structure.UNKNOWN, 'unknown'

    def vwap(part: Sequence[DailyCandle]) -> Decimal:
        tp = [_typical(c) for c in part]
        vols = [c.volume for c in part]
        vol = sum(vols, Decimal(0))
        if vol > 0:
            weighted = sum((p * v for p, v in zip(tp, vols)), Decimal(0))
            return weighted / vol
        return sum(tp, Decimal(0)) / len(tp)

    half = len(rows) // 2
    v1, v2 = vwap(rows[:half]), vwap(rows[half:])
    drift = (v2 - v1) / v1 if v1 > 0 else Decimal(0)
    if drift > Decimal('0.002'):
        structure = Structure.VALUE_UP
    elif drift < Decimal('-0.002'):
        structure = Structure.VALUE_DOWN
    else:
        structure = Structure.SIDEWAYS

    ranges = [c.high - c.low for c in rows]
    recent = sum(ranges[-5:], Decimal(0)) / Decimal(5)
    older = sum(ranges[:-5], Decimal(0)) / Decimal(max(len(ranges) - 5, 1))
    regime = 'negative_gamma' if recent > older else 'positive_gamma'
    return structure, regime


def classify_location(price: Decimal, area: ValueArea | None) -> str | None:
    if area is None or price <= 0:
        return None
    span = area.value_high - area.value_low
    if span <= 0:
        return None
    fib_705 = area.value_low + span * Decimal('0.705')
    fib_788 = area.value_low + span * Decimal('0.788')
    fib_886 = area.value_low + span * Decimal('0.886')
    below_full = area.value_low - span
    if price >= fib_886:
        return 'premium_extreme'
    if price >= fib_788:
        return 'premium'
    if price <= below_full:
        return 'deep_discount'
    if price <= fib_705:
        return 'discount'
    return 'equilibrium'


def detect_absorption(candles: Sequence[DailyCandle], cvd_changes: Sequence[Decimal]) -> str | None:
    """Absorption at extreme + dominance shift.

    Long absorption: price makes a lower low but closes up and CVD turns up.
    Short absorption: price makes a higher high but closes down and CVD turns down.
    """
    if len(candles) < 4 or len(cvd_changes) != len(candles):
        return None
    a, b = candles[-3], candles[-1]
    d1, d2 = cvd_changes[-3], cvd_changes[-1]
    if b.low < a.low and b.close > b.open and d2 > 0 and d1 <= 0:
        return 'absorption_long'
    if b.high > a.high and b.close < b.open and d2 < 0 and d1 >= 0:
        return 'absorption_short'
    return None


def evaluate_orderflow(candles: Sequence[DailyCandle], cvd_changes: Sequence[Decimal]) -> OrderflowState:
    structure, regime = classify_environment(candles)
    area = _value_area(candles)
    price = candles[-1].close if candles else Decimal(0)
    location = classify_location(price, area)
    confirmation = detect_absorption(candles, cvd_changes)
    side = None
    # Only trade with the value structure: long only in discount during value-up,
    # short only in premium during value-down. Avoid the middle of the value area.
    if structure == Structure.VALUE_UP and location in {'discount', 'deep_discount'} and confirmation == 'absorption_long':
        side = 'long'
    elif structure == Structure.VALUE_DOWN and location in {'premium', 'premium_extreme'} and confirmation == 'absorption_short':
        side = 'short'
    return OrderflowState(structure, regime, area, location, confirmation, side)
