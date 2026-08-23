from decimal import Decimal

from abdalghoniy.backtest import replay_counter_trend
from abdalghoniy.fees import CostModel
from abdalghoniy.strategies import Candle, CounterTrendConfig


def test_replay_records_hard_stop_and_net_fee():
    bars = [Candle(100,100,100,100,1), Candle(100,102,100,102,1), Candle(102,102,98,99,1)]
    trades = replay_counter_trend(bars, [Decimal("0"), Decimal("-20"), Decimal("0")], CostModel(Decimal("0"),Decimal("0.0005"),Decimal("0")), CounterTrendConfig(Decimal("50"),Decimal("10")), Decimal("1"), Decimal("2"))
    assert len(trades) == 1
    assert trades[0].exit == Decimal("100")
    assert trades[0].net < Decimal("2")
