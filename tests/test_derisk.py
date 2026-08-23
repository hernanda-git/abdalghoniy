import pytest
from decimal import Decimal
from abdalghoniy.execution import approve_order
from abdalghoniy.monitoring import EdgeDecayMonitor
from abdalghoniy.risk import HardStop
from abdalghoniy.safety import KillSwitch, OrderBook, OrderIntent
from abdalghoniy.validation import GateResult, ValidationLadder


def _gates():
    d='{"dataset_hash":"abc","evaluated_at":"now","code_hash":"def","metric":1}'
    return [GateResult(n, True, d) for n in ValidationLadder.names]


def test_edge_decay_blocks_new_risk_but_not_reduce_only():
    monitor=EdgeDecayMonitor(window=3, compression_ratio=Decimal('0.5'))
    for x in [Decimal('10')]*3+[Decimal('4'),Decimal('3'),Decimal('2')]: monitor.record(x)
    ks=KillSwitch(OrderBook()); ks.arm()
    with pytest.raises(PermissionError):
        approve_order(OrderIntent('e','ETHUSDT'), HardStop.for_entry('long',Decimal('100'),Decimal('2')), ks, _gates(), monitor=monitor)
    result=approve_order(OrderIntent('close','ETHUSDT',reduce_only=True), HardStop.for_entry('long',Decimal('100'),Decimal('2')), ks, _gates(), monitor=monitor)
    assert result.intent.reduce_only
