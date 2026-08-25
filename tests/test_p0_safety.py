import os
from decimal import Decimal

import pytest

from abdalghoniy.config import AppConfig
from abdalghoniy.fees import CostModel, net_pnl
from abdalghoniy.risk import DailyLossBreaker, HardStop, StopSide
from abdalghoniy.safety import KillSwitch, OrderBook, OrderIntent
from abdalghoniy.secrets import load_secrets


def test_kill_switch_halts_on_partition_without_cancelling_protective_orders():
    orders = OrderBook([
        OrderIntent("entry-1", "BTCUSDT", reduce_only=False),
        OrderIntent("stop-1", "BTCUSDT", reduce_only=True, protective=True),
    ])
    switch = KillSwitch(orders)
    switch.arm()
    switch.partition_detected("market-data-timeout")
    assert switch.is_halted()
    assert orders.is_cancelled("entry-1")
    assert not orders.is_cancelled("stop-1")


def test_order_is_rejected_without_armed_kill_switch_or_stop():
    switch = KillSwitch(OrderBook())
    with pytest.raises(PermissionError):
        switch.authorize(OrderIntent("x", "BTCUSDT", reduce_only=False), hard_stop=None, validation_complete=True)


def test_hard_stop_is_directionally_valid_and_rejects_invalid_stop():
    assert HardStop.for_entry("long", Decimal("100"), Decimal("2")) == HardStop(StopSide.SELL, Decimal("98"))
    with pytest.raises(ValueError):
        HardStop.for_entry("long", Decimal("100"), Decimal("0"))
    with pytest.raises(ValueError):
        HardStop(StopSide.SELL, Decimal("0"))


def test_daily_loss_breaker_halts_at_drawdown_cap():
    breaker = DailyLossBreaker(starting_equity=Decimal("1000"), max_loss=Decimal("50"))
    breaker.record_equity(Decimal("950"))
    assert breaker.tripped
    with pytest.raises(PermissionError):
        breaker.allow_new_risk()


def test_net_pnl_subtracts_fee_slippage_and_funding():
    model = CostModel(maker_fee=Decimal("0.0002"), taker_fee=Decimal("0.0005"), slippage_bps=Decimal("2"))
    result = net_pnl(Decimal("10000"), Decimal("100"), Decimal("100"), Decimal("101"), "long", model, funding=Decimal("1"))
    assert result.gross == Decimal("100")
    assert result.total_cost == Decimal("8")
    assert result.net == Decimal("92")


def test_secrets_are_loaded_only_from_environment(monkeypatch):
    monkeypatch.setenv("BITGET_API_KEY", "key-value")
    monkeypatch.setenv("BITGET_API_SECRET", "secret-value")
    monkeypatch.setenv("BITGET_PASSPHRASE", "pass-value")
    secrets = load_secrets()
    assert secrets.api_key == "key-value"
    assert secrets.api_secret == "secret-value"
    assert secrets.passphrase == "pass-value"


def test_config_defaults_are_paper_and_capped():
    cfg = AppConfig.from_mapping({})
    assert cfg.mode == "paper"
    assert cfg.max_leverage <= Decimal("3")
    assert cfg.max_drawdown > 0
