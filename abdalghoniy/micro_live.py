"""Gated micro-live controller.

This module is the ONLY place that may place a real (tiny, capped) order. It encodes the
plan's non-negotiable invariant: no live order is allowed unless:
  - the validation ladder (gates 1-5) passed on independent data, AND
  - a promotion registry holds immutable evidence of positive post-fee expectancy with a
    statistical lower bound > 0 and positive random-control uplift, AND
  - a hard stop is attached, AND
  - the kill-switch is armed (never halts protective reduce-only orders).

Your approval ("you own all permissions") does NOT bypass the ladder. The ladder is enforced
in code so that even an authorized operator cannot accidentally skip it. This is the governance
hole the plan explicitly forbids: any override gets refused here.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from .fees import CostModel, net_pnl
from .promotion import PromotionEvidence, PromotionRegistry
from .risk import DailyLossBreaker, HardStop
from .safety import KillSwitch, OrderBook, OrderIntent
from .secrets import load_secrets


@dataclass(frozen=True)
class MicroLiveGate:
    authorized_by_user: bool
    promotion: Optional[PromotionEvidence]
    kill_switch_armed: bool
    kill_switch_halted: bool
    hard_stop: Optional[HardStop]
    daily_breaker_tripped: bool

    def allow_trade(self) -> tuple[bool, str]:
        if not self.authorized_by_user:
            return False, "user authorization missing"
        if self.promotion is None or not self.promotion.eligible():
            return False, "promotion evidence absent or ineligible (ladder gates 1-5 not passed on independent data)"
        if not self.kill_switch_armed:
            return False, "kill-switch not armed"
        if self.kill_switch_halted:
            return False, "kill-switch halted"
        if self.hard_stop is None:
            return False, "hard stop mandatory"
        if self.daily_breaker_tripped:
            return False, "daily loss breaker tripped"
        return True, "ok"


@dataclass(frozen=True)
class MicroLiveResult:
    allowed: bool
    reason: str
    order_id: Optional[str] = None
    side: Optional[str] = None
    qty: Optional[str] = None
    note: str = ""


class MicroLiveController:
    """Computes whether a (tiny, capped) demo order is permitted. Placement is delegated to
    an injected adapter so this module stays testable without network/orders."""

    def __init__(self, promotion_path, *, max_notional: Decimal = Decimal("10"), max_leverage: int = 3):
        self.promotion = PromotionRegistry(promotion_path)
        self.max_notional = max_notional
        self.max_leverage = max_leverage

    def evaluate(self, *, user_authorized: bool, kill_switch: KillSwitch, hard_stop: HardStop, daily_breaker: DailyLossBreaker, symbol: str, direction: str, entry: Decimal, size: Decimal) -> MicroLiveGate:
        promo = self.promotion.load()
        return MicroLiveGate(
            authorized_by_user=user_authorized,
            promotion=promo,
            kill_switch_armed=kill_switch._armed,  # noqa: access for gate check
            kill_switch_halted=kill_switch.is_halted(),
            hard_stop=hard_stop,
            daily_breaker_tripped=daily_breaker.tripped,
        )

    def attempt_order(self, *, user_authorized: bool, kill_switch: KillSwitch, hard_stop: HardStop, daily_breaker: DailyLossBreaker, symbol: str, direction: str, entry: Decimal, notional: Decimal, adverse_move_bps: Decimal, place_fn) -> MicroLiveResult:
        if notional > self.max_notional:
            return MicroLiveResult(False, f"notional {notional} exceeds cap {self.max_notional}", note="structural cap")
        gate = self.evaluate(user_authorized=user_authorized, kill_switch=kill_switch, hard_stop=hard_stop, daily_breaker=daily_breaker, symbol=symbol, direction=direction, entry=entry, size=Decimal("0"))
        ok, reason = gate.allow_trade()
        if not ok:
            return MicroLiveResult(False, reason)
        # Place the protective stop first, then the entry, via the injected adapter.
        stop = HardStop.for_entry(direction, entry, entry * adverse_move_bps / Decimal("10000"))
        order_id = place_fn(symbol=symbol, direction=direction, notional=notional, hard_stop=stop)
        return MicroLiveResult(True, "ok", order_id=order_id, side=direction, qty=str(notional))
