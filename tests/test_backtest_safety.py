from decimal import Decimal
from abdalghoniy.backtest import replay_counter_trend
from abdalghoniy.fees import CostModel
from abdalghoniy.strategies import Candle, CounterTrendConfig


def test_replay_applies_funding_filter_and_skips_overlap():
    bars=[Candle(100,100,100,100,1),Candle(100,102,100,102,1),Candle(102,103,101,102,1),Candle(102,102,98,99,1),Candle(99,101,98,100,1)]
    cvd=[Decimal('0'),Decimal('-20'),Decimal('-20'),Decimal('-20'),Decimal('0')]
    funding=[Decimal('0'),Decimal('100'),Decimal('0'),Decimal('0'),Decimal('0')]
    trades=replay_counter_trend(bars,cvd,CostModel(Decimal('0'),Decimal('0'),Decimal('0')),CounterTrendConfig(Decimal('50'),Decimal('10'),Decimal('20')),Decimal('1'),Decimal('2'),funding_bps=funding)
    assert trades == []
