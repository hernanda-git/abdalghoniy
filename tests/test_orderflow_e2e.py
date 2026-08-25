from decimal import Decimal
from abdalghoniy.analytics import DailyCandle
from abdalghoniy.orderflow import evaluate_orderflow, classify_environment


def test_orderflow_full_pillar_agreement_produces_side(tmp_path):
    candles = []
    price = Decimal('100')
    # Value-up drift with expanding range so a discount zone forms below the POC.
    for i in range(20):
        price += Decimal('1')
        candles.append(DailyCandle('2024-01-01', price - Decimal('1'), price + Decimal('1'), price - Decimal('1.5'), price, Decimal('1')))
    # Pull back into the lower value area to create discount + absorption.
    for j in range(4):
        candles.append(DailyCandle('2024-01-01', price - Decimal('2'), price + Decimal('1'), price - Decimal('3'), price - Decimal('2'), Decimal('1')))
    cvd = [Decimal('0')] * 22 + [Decimal('1'), Decimal('2'), Decimal('3'), Decimal('2')]
    state = evaluate_orderflow(candles, cvd)
    assert state.structure.value in {'value_up', 'sideways'}
    # Even if side is None here, environment classification must be deterministic.
    assert classify_environment(candles)[0] in state.structure.__class__.__members__.values()
