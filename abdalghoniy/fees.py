from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostModel:
    maker_fee: Decimal
    taker_fee: Decimal
    slippage_bps: Decimal


@dataclass(frozen=True)
class Pnl:
    gross: Decimal
    total_cost: Decimal
    net: Decimal


def net_pnl(notional: Decimal, quantity: Decimal, entry: Decimal, exit: Decimal, direction: str, model: CostModel, funding: Decimal = Decimal("0")) -> Pnl:
    if notional <= 0 or quantity <= 0:
        raise ValueError("notional and quantity must be positive")
    gross = (exit - entry) * quantity if direction.lower() == "long" else (entry - exit) * quantity
    fees = notional * (model.maker_fee + model.taker_fee)
    slippage = notional * model.slippage_bps / Decimal("10000")
    total_cost = fees + slippage - funding
    return Pnl(gross=gross, total_cost=total_cost, net=gross - total_cost)
