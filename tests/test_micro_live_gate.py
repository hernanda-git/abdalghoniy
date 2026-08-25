from decimal import Decimal
from abdalghoniy.micro_live import MicroLiveController, MicroLiveGate, MicroLiveResult
from abdalghoniy.promotion import PromotionEvidence, PromotionRegistry
from abdalghoniy.risk import DailyLossBreaker, HardStop
from abdalghoniy.safety import KillSwitch, OrderBook, OrderIntent


def _ks():
    ks = KillSwitch(OrderBook([OrderIntent('stop1', 'SBTCSUSDT', reduce_only=True, protective=True)]))
    ks.arm()
    return ks


def _breaker():
    return DailyLossBreaker(Decimal('3000'), Decimal('90'), state_path=None)


def test_micro_live_refuses_without_promotion_evidence(tmp_path):
    ctrl = MicroLiveController(tmp_path / 'promo.json')
    gate = ctrl.evaluate(user_authorized=True, kill_switch=_ks(), hard_stop=HardStop.for_entry('long', 100, 2), daily_breaker=_breaker(), symbol='SBTCSUSDT', direction='long', entry=Decimal('100'), size=Decimal('1'))
    ok, reason = gate.allow_trade()
    assert ok is False and 'promotion' in reason


def test_micro_live_refuses_without_user_authorization(tmp_path):
    promo = PromotionEvidence('orderflow', 'd', 'c', 'g', 100, 0.1, 0.05, 0.2, True)
    reg = PromotionRegistry(tmp_path / 'promo.json'); reg.save(promo)
    ctrl = MicroLiveController(tmp_path / 'promo.json')
    gate = ctrl.evaluate(user_authorized=False, kill_switch=_ks(), hard_stop=HardStop.for_entry('long', 100, 2), daily_breaker=_breaker(), symbol='SBTCSUSDT', direction='long', entry=Decimal('100'), size=Decimal('1'))
    ok, reason = gate.allow_trade()
    assert ok is False and 'authorization' in reason


def test_micro_live_allows_when_ladder_passed_and_user_authorized(tmp_path):
    promo = PromotionEvidence('orderflow', 'd', 'c', 'g', 100, 0.1, 0.05, 0.2, True)
    reg = PromotionRegistry(tmp_path / 'promo.json'); reg.save(promo)
    ctrl = MicroLiveController(tmp_path / 'promo.json')
    placed = {}
    def place_fn(*, symbol, direction, notional, hard_stop):
        placed['id'] = f"{symbol}-{direction}"
        return placed['id']
    res = ctrl.attempt_order(user_authorized=True, kill_switch=_ks(), hard_stop=HardStop.for_entry('long', 100, 2), daily_breaker=_breaker(), symbol='SBTCSUSDT', direction='long', entry=Decimal('100'), notional=Decimal('10'), adverse_move_bps=Decimal('10'), place_fn=place_fn)
    assert res.allowed is True and res.order_id == 'SBTCSUSDT-long'


def test_micro_live_rejects_over_cap(tmp_path):
    promo = PromotionEvidence('orderflow', 'd', 'c', 'g', 100, 0.1, 0.05, 0.2, True)
    reg = PromotionRegistry(tmp_path / 'promo.json'); reg.save(promo)
    ctrl = MicroLiveController(tmp_path / 'promo.json')
    res = ctrl.attempt_order(user_authorized=True, kill_switch=_ks(), hard_stop=HardStop.for_entry('long', 100, 2), daily_breaker=_breaker(), symbol='SBTCSUSDT', direction='long', entry=Decimal('100'), notional=Decimal('50'), adverse_move_bps=Decimal('10'), place_fn=lambda **k: 'x')
    assert res.allowed is False and 'cap' in res.reason
