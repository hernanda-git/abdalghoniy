from decimal import Decimal

from abdalghoniy.strategies import funding_carry_signal, mean_reversion_signal
from abdalghoniy.monitoring import EdgeDecayMonitor


def test_funding_carry_direction_and_mean_reversion_signal():
    assert funding_carry_signal(Decimal("8"), Decimal("5")) == "short"
    assert funding_carry_signal(Decimal("-8"), Decimal("5")) == "long"
    assert mean_reversion_signal(Decimal("110"), Decimal("100"), Decimal("4"), Decimal("75")) == "short"


def test_edge_decay_derisks_when_recent_expectancy_compresses():
    monitor = EdgeDecayMonitor(window=3, compression_ratio=Decimal("0.5"))
    for x in [Decimal("10"), Decimal("10"), Decimal("10")]:
        monitor.record(x)
    assert not monitor.derisk
    for x in [Decimal("4"), Decimal("3"), Decimal("2")]:
        monitor.record(x)
    assert monitor.derisk
