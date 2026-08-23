import pytest
from decimal import Decimal
from abdalghoniy.account import AccountSimulator
from abdalghoniy.fees import CostModel


def test_account_simulator_enforces_notional_and_no_overlap():
    sim=AccountSimulator(Decimal('1000'),Decimal('500'),Decimal('3'),CostModel(Decimal('0'),Decimal('0'),Decimal('0')))
    sim.enter('ETHUSDT','long',Decimal('100'),Decimal('5'))
    with pytest.raises(PermissionError): sim.enter('ETHUSDT','short',Decimal('100'),Decimal('1'))
    sim.exit(Decimal('100'))
    with pytest.raises(ValueError): sim.enter('BTCUSDT','long',Decimal('100'),Decimal('6'))
    sim.enter('ETHUSDT','long',Decimal('100'),Decimal('5'))
    trade=sim.exit(Decimal('101'))
    assert trade.net == Decimal('5')
    assert sim.equity == Decimal('1005')
