from decimal import Decimal

from abdalghoniy.backtest import counter_trend_diagnostics, replay_counter_trend
from abdalghoniy.fees import CostModel
from abdalghoniy.strategies import Candle, CounterTrendConfig


def test_replay_records_hard_stop_and_net_fee():
    bars = [Candle(100,100,100,100,1), Candle(100,102,100,102,1), Candle(102,102,98,99,1)]
    trades = replay_counter_trend(bars, [Decimal("0"), Decimal("-20"), Decimal("0")], CostModel(Decimal("0"),Decimal("0.0005"),Decimal("0")), CounterTrendConfig(Decimal("50"),Decimal("10")), Decimal("1"), Decimal("2"))
    assert len(trades) == 1
    assert trades[0].exit == Decimal("100")
    assert trades[0].net < Decimal("2")


def test_replay_charges_funding_in_net_pnl():
    bars = [Candle(100,100,100,100,1), Candle(100,102,100,102,1), Candle(102,102,102,102,1)]
    no_funding = replay_counter_trend(bars, [Decimal("0"), Decimal("-20"), Decimal("0")], CostModel(Decimal("0"),Decimal("0"),Decimal("0")), CounterTrendConfig(Decimal("50"),Decimal("10")), Decimal("1"), Decimal("2"), funding_bps=[Decimal("0"), Decimal("0"), Decimal("0")])
    with_funding = replay_counter_trend(bars, [Decimal("0"), Decimal("-20"), Decimal("0")], CostModel(Decimal("0"),Decimal("0"),Decimal("0")), CounterTrendConfig(Decimal("50"),Decimal("10")), Decimal("1"), Decimal("2"), funding_bps=[Decimal("0"), Decimal("10"), Decimal("0")])
    assert no_funding[0].direction == "short"
    assert with_funding[0].funding == Decimal("0.102")
    assert with_funding[0].net == no_funding[0].net + Decimal("0.102")


def test_counter_trend_diagnostics_identifies_missing_cvd_and_threshold_blockers():
    bars = [Candle("100", "100.1", "99.9", "100", "1"), Candle("100", "100.2", "99.9", "100.1", "1"), Candle("100.1", "100.3", "100", "100.2", "1")]
    result = counter_trend_diagnostics(bars, [Decimal("0")] * 3, CounterTrendConfig())
    assert result["rows"] == 3
    assert result["cvd_nonzero"] == 0
    assert result["momentum_abs_ge_threshold"] == 0
    assert result["blocked_by_cvd"] == 0
    assert result["candidate_signals"] == 0
