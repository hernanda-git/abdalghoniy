from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence


@dataclass(frozen=True)
class Candle:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __init__(self, open, high, low, close, volume):
        object.__setattr__(self, "open", Decimal(str(open)))
        object.__setattr__(self, "high", Decimal(str(high)))
        object.__setattr__(self, "low", Decimal(str(low)))
        object.__setattr__(self, "close", Decimal(str(close)))
        object.__setattr__(self, "volume", Decimal(str(volume)))


@dataclass(frozen=True)
class CounterTrendConfig:
    momentum_bps: Decimal = Decimal("50")
    min_cvd_reversal: Decimal = Decimal("10")
    max_funding_abs_bps: Decimal = Decimal("20")


def counter_trend_signal(candles: Sequence[Candle], cvd_change: Decimal, config: CounterTrendConfig, funding_bps: Decimal = Decimal("0")) -> Optional[str]:
    if len(candles) < 2 or abs(funding_bps) > config.max_funding_abs_bps:
        return None
    previous, current = candles[-2], candles[-1]
    if previous.close <= 0:
        return None
    momentum_bps = (current.close - previous.close) / previous.close * Decimal("10000")
    if momentum_bps >= config.momentum_bps and cvd_change <= -config.min_cvd_reversal:
        return "short"
    if momentum_bps <= -config.momentum_bps and cvd_change >= config.min_cvd_reversal:
        return "long"
    return None


def funding_carry_signal(funding_bps: Decimal, threshold_bps: Decimal) -> Optional[str]:
    if funding_bps >= threshold_bps:
        return "short"
    if funding_bps <= -threshold_bps:
        return "long"
    return None


def mean_reversion_signal(price: Decimal, mean: Decimal, atr: Decimal, rsi: Decimal, band_atr: Decimal = Decimal("2")) -> Optional[str]:
    if atr <= 0 or mean <= 0:
        return None
    if price >= mean + band_atr * atr and rsi >= Decimal("70"):
        return "short"
    if price <= mean - band_atr * atr and rsi <= Decimal("30"):
        return "long"
    return None
