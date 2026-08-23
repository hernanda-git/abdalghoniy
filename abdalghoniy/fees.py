from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostModel:
    maker_fee: Decimal
    taker_fee: Decimal
    slippage_bps: Decimal

    def __post_init__(self):
        if any(x.is_nan() or x.is_infinite() or x < 0 for x in (self.maker_fee, self.taker_fee, self.slippage_bps)):
            raise ValueError('fee and slippage values must be finite and non-negative')


@dataclass(frozen=True)
class Pnl:
    gross: Decimal
    total_cost: Decimal
    net: Decimal


def net_pnl(notional: Decimal, quantity: Decimal, entry: Decimal, exit: Decimal, direction: str, model: CostModel, funding: Decimal = Decimal('0')) -> Pnl:
    if direction.lower() not in {'long', 'short'}:
        raise ValueError('direction must be long or short')
    if notional <= 0 or quantity <= 0 or entry <= 0 or exit <= 0:
        raise ValueError('notional, quantity, and prices must be positive')
    gross = (exit - entry) * quantity if direction.lower() == 'long' else (entry - exit) * quantity
    fees = notional * (model.maker_fee + model.taker_fee)
    slippage = notional * model.slippage_bps / Decimal('10000')
    total_cost = fees + slippage - funding
    return Pnl(gross=gross, total_cost=total_cost, net=gross - total_cost)
