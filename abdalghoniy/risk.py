from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class StopSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class HardStop:
    side: StopSide
    price: Decimal

    def __post_init__(self):
        if self.price <= 0:
            raise ValueError("stop price must be positive")

    @classmethod
    def for_entry(cls, direction: str, entry: Decimal, distance: Decimal) -> "HardStop":
        if entry <= 0 or distance <= 0:
            raise ValueError("entry and stop distance must be positive")
        if direction.lower() == "long":
            return cls(StopSide.SELL, entry - distance)
        if direction.lower() == "short":
            return cls(StopSide.BUY, entry + distance)
        raise ValueError("direction must be long or short")


class DailyLossBreaker:
    def __init__(self, starting_equity: Decimal, max_loss: Decimal):
        if starting_equity <= 0 or max_loss <= 0:
            raise ValueError("equity and loss cap must be positive")
        self.starting_equity = starting_equity
        self.max_loss = max_loss
        self.tripped = False

    def record_equity(self, equity: Decimal) -> None:
        if equity <= self.starting_equity - self.max_loss:
            self.tripped = True

    def allow_new_risk(self) -> None:
        if self.tripped:
            raise PermissionError("daily loss breaker is tripped")
