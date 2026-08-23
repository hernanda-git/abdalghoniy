from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .fees import CostModel, Pnl, net_pnl


@dataclass(frozen=True)
class Position:
    symbol: str
    direction: str
    entry: Decimal
    quantity: Decimal


class AccountSimulator:
    def __init__(self, starting_equity: Decimal, max_position_notional: Decimal, max_leverage: Decimal, cost_model: CostModel):
        if starting_equity <= 0 or max_position_notional <= 0 or max_leverage <= 0:
            raise ValueError('account limits must be positive')
        self.equity = starting_equity
        self.max_position_notional = max_position_notional
        self.max_leverage = max_leverage
        self.cost_model = cost_model
        self.position: Optional[Position] = None

    def enter(self, symbol: str, direction: str, entry: Decimal, quantity: Decimal) -> Position:
        if self.position is not None:
            raise PermissionError('overlapping positions are disabled')
        notional = entry * quantity
        if notional <= 0 or notional > self.max_position_notional or notional > self.equity * self.max_leverage:
            raise ValueError('position exceeds account limits')
        self.position = Position(symbol, direction, entry, quantity)
        return self.position

    def exit(self, price: Decimal) -> Pnl:
        if self.position is None:
            raise PermissionError('no open position')
        p = self.position
        result = net_pnl(p.entry * p.quantity, p.quantity, p.entry, price, p.direction, self.cost_model)
        self.equity += result.net
        self.position = None
        return result
