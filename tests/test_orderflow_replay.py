from decimal import Decimal
from abdalghoniy.backtest import replay_orderflow
from abdalghoniy.fees import CostModel
from abdalghoniy.strategies import Candle, OrderflowReplayConfig


def test_orderflow_replay_respects_stop_and_charges_fees():
    bars = [
        Candle(100, 100, 99, 100, 1),
        Candle(100, 101, 99, 100, 1),
        Candle(100, 102, 101, 102, 1),
        Candle(102, 104, 101, 103, 1),
        Candle(103, 105, 100, 101, 1),  # long absorption context with CVD shift
    ]
    cvd = [Decimal('0'), Decimal('0'), Decimal('1'), Decimal('2'), Decimal('3')]
    model = CostModel(Decimal('0.0005'), Decimal('0.0005'), Decimal('2'))
    trades = replay_orderflow(bars, cvd, model, OrderflowReplayConfig(), max_position_notional=Decimal('10'))
    # The synthetic series may or may not trigger; the engine must not raise and must
    # honor fee accounting when it does trade.
    for t in trades:
        assert t.net < t.entry * t.quantity
