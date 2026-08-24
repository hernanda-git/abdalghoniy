from decimal import Decimal

from abdalghoniy.data import aggregate_cvd, align_funding


def test_aggregate_cvd_uses_public_trade_side_and_size_per_candle():
    timestamps = ["2026-08-24T00:00:00+00:00", "2026-08-24T00:01:00+00:00"]
    fills = [
        {"ts": "1787529601000", "size": "2.5", "side": "Buy"},
        {"ts": "1787529630000", "size": "1.0", "side": "Sell"},
        {"ts": "1787529661000", "size": "3.0", "side": "Buy"},
    ]
    assert aggregate_cvd(timestamps, fills, "1m") == [Decimal("1.5"), Decimal("3.0")]


def test_align_funding_uses_latest_event_at_or_before_candle():
    timestamps = ["2026-08-24T00:00:00+00:00", "2026-08-24T08:00:00+00:00"]
    rows = [
        {"fundingTime": "1787529600000", "fundingRate": "0.0001"},
        {"fundingTime": "1787558400000", "fundingRate": "-0.0002"},
    ]
    assert align_funding(timestamps, rows) == [Decimal("1"), Decimal("-2")]
