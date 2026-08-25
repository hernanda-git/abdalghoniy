from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional

from .fees import CostModel, net_pnl
from .strategies import (
    Candle, CounterTrendConfig, OrderflowReplayConfig, counter_trend_signal, orderflow_signal,
)


@dataclass(frozen=True)
class Trade:
    direction: str
    entry: Decimal
    exit: Decimal
    quantity: Decimal
    net: Decimal
    bars_held: int
    funding: Decimal = Decimal("0")


def counter_trend_diagnostics(candles: Iterable[Candle], cvd_changes: Iterable[Decimal], config: CounterTrendConfig, funding_bps: Optional[Iterable[Decimal]] = None) -> dict:
    bars = list(candles)
    cvds = list(cvd_changes)
    funding = list(funding_bps) if funding_bps is not None else [Decimal('0')] * len(bars)
    if len(cvds) != len(bars) or len(funding) != len(bars):
        raise ValueError('market features must align with candles')
    result = {
        'rows': len(bars),
        'usable_signal_rows': max(0, len(bars) - 2),
        'cvd_nonzero': sum(1 for value in cvds if value != 0),
        'funding_nonzero': sum(1 for value in funding if value != 0),
        'funding_rejects': 0,
        'momentum_up': 0,
        'momentum_down': 0,
        'momentum_neutral': 0,
        'momentum_abs_ge_threshold': 0,
        'blocked_by_cvd': 0,
        'candidate_signals': 0,
    }
    for i in range(1, len(bars) - 1):
        if abs(funding[i]) > config.max_funding_abs_bps:
            result['funding_rejects'] += 1
            continue
        previous, current = bars[i - 1], bars[i]
        if previous.close <= 0:
            result['momentum_neutral'] += 1
            continue
        momentum_bps = (current.close - previous.close) / previous.close * Decimal('10000')
        if abs(momentum_bps) >= config.momentum_bps:
            result['momentum_abs_ge_threshold'] += 1
        direction = 'short' if momentum_bps >= config.momentum_bps else 'long' if momentum_bps <= -config.momentum_bps else None
        if direction == 'short':
            result['momentum_up'] += 1
            signal = cvds[i] <= -config.min_cvd_reversal
        elif direction == 'long':
            result['momentum_down'] += 1
            signal = cvds[i] >= config.min_cvd_reversal
        else:
            result['momentum_neutral'] += 1
            continue
        if signal:
            result['candidate_signals'] += 1
        else:
            result['blocked_by_cvd'] += 1
    result['cvd_missing_all'] = result['cvd_nonzero'] == 0
    return result


def replay_counter_trend(candles: Iterable[Candle], cvd_changes: Iterable[Decimal], model: CostModel, config: CounterTrendConfig, stop_distance: Decimal, target_distance: Decimal, max_hold: int = 5, funding_bps: Optional[Iterable[Decimal]] = None, max_position_notional: Optional[Decimal] = None) -> List[Trade]:
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
        quantity = Decimal('1') if max_position_notional is None else min(Decimal('1'), max_position_notional / entry)
        if quantity <= 0:
            continue
        notional = entry * quantity
        funding_cash = -notional * funding[i] / Decimal('10000') if direction == 'long' else notional * funding[i] / Decimal('10000')
        pnl = net_pnl(notional, quantity, entry, exit_price, direction, model, funding=funding_cash)
        trades.append(Trade(direction, entry, exit_price, quantity, pnl.net, held, funding_cash))
        next_entry = i + held + 1
    return trades


def replay_orderflow(candles, cvd_changes, model, config=None, *, max_position_notional=None, max_hold=None):
    config = config or OrderflowReplayConfig()
    hold = max_hold or config.max_hold
    bars = list(candles)
    cvds = list(cvd_changes)
    if len(cvds) != len(bars):
        raise ValueError('market features must align with candles')
    trades: List[Trade] = []
    next_entry = 0
    for i in range(len(bars) - 1):
        if i < next_entry:
            continue
        side = orderflow_signal(bars[:i+1], cvds[i])
        if not side:
            continue
        entry = bars[i].close
        stop_dist = entry * config.stop_distance_bps / Decimal('10000')
        target_dist = entry * config.target_distance_bps / Decimal('10000')
        stop = entry - stop_dist if side == 'long' else entry + stop_dist
        target = entry + target_dist if side == 'long' else entry - target_dist
        end = min(i + hold, len(bars) - 1)
        exit_price, held = bars[end].close, end - i
        for j in range(i + 1, end + 1):
            bar = bars[j]
            if side == 'long':
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
        quantity = Decimal('1') if max_position_notional is None else min(Decimal('1'), max_position_notional / entry)
        if quantity <= 0:
            continue
        notional = entry * quantity
        pnl = net_pnl(notional, quantity, entry, exit_price, side, model)
        trades.append(Trade(side, entry, exit_price, quantity, pnl.net, held))
        next_entry = i + held + 1
    return trades
