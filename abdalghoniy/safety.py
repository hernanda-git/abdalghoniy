from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .risk import HardStop


@dataclass(frozen=True)
class OrderIntent:
    order_id: str
    symbol: str
    reduce_only: bool = False
    protective: bool = False


class OrderBook:
    def __init__(self, orders=None):
        self.orders = {o.order_id: o for o in (orders or [])}
        self.cancelled = set()

    def is_cancelled(self, order_id: str) -> bool:
        return order_id in self.cancelled

    def cancel_non_protective(self) -> None:
        self.cancelled.update(
            o.order_id for o in self.orders.values() if not (o.reduce_only and o.protective)
        )


class KillSwitch:
    def __init__(self, orders: OrderBook):
        self.orders = orders
        self._armed = False
        self._halted = False
        self.reason: Optional[str] = None

    def arm(self) -> None:
        self._armed = True

    def is_halted(self) -> bool:
        return self._halted

    def partition_detected(self, reason: str) -> None:
        self._halted = True
        self.reason = reason
        self.orders.cancel_non_protective()

    def authorize(self, intent: OrderIntent, hard_stop: Optional[HardStop], validation_complete: bool) -> None:
        if self._halted or not self._armed:
            raise PermissionError("kill-switch is not armed for trading")
        if not validation_complete:
            raise PermissionError("validation ladder incomplete")
        if hard_stop is None:
            raise PermissionError("hard stop is mandatory")
