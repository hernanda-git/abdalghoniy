from decimal import Decimal

from abdalghoniy.strategies import Candle, CounterTrendConfig, counter_trend_signal
from abdalghoniy.validation import ValidationLadder, purged_splits


def test_counter_trend_fades_extreme_only_with_exhaustion():
    cfg = CounterTrendConfig(momentum_bps=Decimal("50"), min_cvd_reversal=Decimal("10"))
    candles = [Candle(100, 100, 100, 100, 10), Candle(100, 101, 100, 101, 10)]
    assert counter_trend_signal(candles, cvd_change=Decimal("-20"), config=cfg) == "short"
    assert counter_trend_signal(candles, cvd_change=Decimal("20"), config=cfg) is None


def test_cost_and_expectancy_gates_reject_negative_net_edge():
    ladder = ValidationLadder()
    assert not ladder.can_trade(cost_edge_bps=Decimal("8"), round_trip_fee_bps=Decimal("10"), expectancy=Decimal("1"))
    assert not ladder.can_trade(cost_edge_bps=Decimal("20"), round_trip_fee_bps=Decimal("10"), expectancy=Decimal("-1"))
    assert ladder.can_trade(cost_edge_bps=Decimal("25"), round_trip_fee_bps=Decimal("10"), expectancy=Decimal("1"))


def test_purged_splits_have_embargo_and_no_overlap():
    splits = purged_splits(100, folds=5, purge=3, embargo=2)
    for train, test in splits:
        assert set(train).isdisjoint(test)
        lo, hi = min(test), max(test)
        assert all(not (lo - 3 <= idx <= hi + 2) for idx in train)
