from decimal import Decimal
from abdalghoniy.analytics import DailyCandle
from abdalghoniy.orderflow import (
    ValueArea, classify_environment, classify_location, detect_absorption, evaluate_orderflow,
)


def _candle(o, h, l, c, v=Decimal('1')):
    return DailyCandle('2024-01-01', o, max(h, o, c), min(l, o, c), c, v)


def test_environment_distinguishes_value_up_and_down():
    up = [_candle(Decimal(100), Decimal(101), Decimal(99), Decimal(100 + i)) for i in range(20)]
    down = [_candle(Decimal(100), Decimal(101), Decimal(99), Decimal(100 - i)) for i in range(20)]
    assert classify_environment(up)[0].value == 'value_up'
    assert classify_environment(down)[0].value == 'value_down'


def test_location_reports_discount_outside_value_area():
    area = ValueArea(Decimal('100'), Decimal('110'), Decimal('90'))
    assert classify_location(Decimal('92'), area) == 'discount'
    assert classify_location(Decimal('105'), area) == 'equilibrium'


def test_absorption_requires_cvd_shift():
    candles = [
        _candle(Decimal(100), Decimal(101), Decimal(99), Decimal(100)),
        _candle(Decimal(99), Decimal(100), Decimal(98), Decimal(99)),
        _candle(Decimal(98), Decimal(99), Decimal(97), Decimal(98)),
        _candle(Decimal(97), Decimal(98.5), Decimal(96), Decimal(98)),
    ]
    cvd = [Decimal('0'), Decimal('-1'), Decimal('-2'), Decimal('1')]
    assert detect_absorption(candles, cvd) == 'absorption_long'
    # Without CVD shift there is no confirmation.
    assert detect_absorption(candles, [Decimal('0')]*4) is None


def test_orderflow_only_proposes_with_full_pillar_agreement():
    candles = [
        _candle(Decimal(100), Decimal(101), Decimal(99), Decimal(100 + i)) for i in range(10)
    ] + [
        _candle(Decimal(110), Decimal(112), Decimal(109), Decimal(111)),
        _candle(Decimal(111), Decimal(113), Decimal(110), Decimal(112)),
        _candle(Decimal(112), Decimal(114), Decimal(111), Decimal(113)),
        _candle(Decimal(113), Decimal(115), Decimal(112), Decimal(114.5)),
    ]
    cvd = [Decimal('0')]*13 + [Decimal('1')]
    state = evaluate_orderflow(candles, cvd)
    # No discount zone in this synthetic up-move, so side stays None.
    assert state.side is None
