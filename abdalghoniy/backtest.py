from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List

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


def replay_counter_trend(candles: Iterable[Candle], cvd_changes: Iterable[Decimal], model: CostModel, config: CounterTrendConfig, stop_distance: Decimal, target_distance: Decimal, max_hold: int = 5) -> List[Trade]:
    bars = list(candles)
    cvds = list(cvd_changes)
    trades: List[Trade] = []
    for i in range(1, len(bars) - 1):
        direction = counter_trend_signal(bars[i-1:i+1], cvds[i], config)
        if not direction:
            continue
        entry = bars[i].close
        stop = entry - stop_distance if direction == "long" else entry + stop_distance
        target = entry + target_distance if direction == "long" else entry - target_distance
        exit_price, held = bars[min(i + max_hold, len(bars)-1)].close, min(max_hold, len(bars)-1-i)
        reason = "max_hold"
        for j in range(i + 1, min(i + max_hold, len(bars)-1) + 1):
            bar = bars[j]
            if direction == "long":
                if bar.low <= stop:
                    exit_price, held, reason = stop, j-i, "hard_stop"
                    break
                if bar.high >= target:
                    exit_price, held, reason = target, j-i, "target"
                    break
            else:
                if bar.high >= stop:
                    exit_price, held, reason = stop, j-i, "hard_stop"
                    break
                if bar.low <= target:
                    exit_price, held, reason = target, j-i, "target"
                    break
        pnl = net_pnl(entry * Decimal("1"), Decimal("1"), entry, exit_price, direction, model)
        trades.append(Trade(direction, entry, exit_price, Decimal("1"), pnl.net, held))
    return trades
