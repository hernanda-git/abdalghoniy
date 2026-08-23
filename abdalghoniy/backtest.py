from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional

from .fees import CostModel, net_pnl
from .strategies import Candle, CounterTrendConfig, counter_trend_signal


@dataclass(frozen=True)
class Trade:
    direction: str
    entry: Decimal
    exit: Decimal
    quantity: Decimal
    net: Decimal
    bars_held: int


def replay_counter_trend(candles: Iterable[Candle], cvd_changes: Iterable[Decimal], model: CostModel, config: CounterTrendConfig, stop_distance: Decimal, target_distance: Decimal, max_hold: int = 5, funding_bps: Optional[Iterable[Decimal]] = None) -> List[Trade]:
    bars = list(candles)
    cvds = list(cvd_changes)
    funding = list(funding_bps) if funding_bps is not None else [Decimal('0')] * len(bars)
    if len(cvds) != len(bars) or len(funding) != len(bars):
        raise ValueError('market features must align with candles')
    trades: List[Trade] = []
    next_entry = 1
    for i in range(1, len(bars) - 1):
        if i < next_entry:
            continue
        direction = counter_trend_signal(bars[i-1:i+1], cvds[i], config, funding_bps=funding[i])
        if not direction:
            continue
        entry = bars[i].close
        stop = entry - stop_distance if direction == 'long' else entry + stop_distance
        target = entry + target_distance if direction == 'long' else entry - target_distance
        end = min(i + max_hold, len(bars) - 1)
        exit_price, held = bars[end].close, end - i
        for j in range(i + 1, end + 1):
            bar = bars[j]
            if direction == 'long':
                if bar.low <= stop:
                    exit_price, held = stop, j - i
                    break
                if bar.high >= target:
                    exit_price, held = target, j - i
                    break
            else:
                if bar.high >= stop:
                    exit_price, held = stop, j - i
                    break
                if bar.low <= target:
                    exit_price, held = target, j - i
                    break
        pnl = net_pnl(entry, Decimal('1'), entry, exit_price, direction, model)
        trades.append(Trade(direction, entry, exit_price, Decimal('1'), pnl.net, held))
        next_entry = i + held + 1
    return trades
