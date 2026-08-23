from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .monitoring import EdgeDecayMonitor
from .risk import HardStop
from .safety import KillSwitch, OrderIntent
from .validation import GateResult, ValidationLadder


@dataclass(frozen=True)
class ApprovedOrder:
    intent: OrderIntent
    stop: HardStop


def approve_order(intent: OrderIntent, stop: HardStop, kill_switch: KillSwitch, gates: Sequence[GateResult], monitor: EdgeDecayMonitor | None = None) -> ApprovedOrder:
    if monitor is not None and monitor.derisk and not intent.reduce_only:
        raise PermissionError("edge decay derisk blocks new risk")
    if not ValidationLadder().authorize(list(gates)):
        raise PermissionError("all six validation gates are required")
    kill_switch.authorize(intent, stop, validation_complete=True)
    return ApprovedOrder(intent, stop)
