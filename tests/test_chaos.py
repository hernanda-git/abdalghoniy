import pytest

from abdalghoniy.chaos import ChaosVenue


def test_chaos_venue_blocks_entries_but_allows_protective_close():
    venue = ChaosVenue()
    venue.partition("network down")
    with pytest.raises(PermissionError):
        venue.entry("BTCUSDT", 100)
    assert venue.protective_close("BTCUSDT", 1)["status"] == "closed"


def test_chaos_venue_reconciles_after_reconnect():
    venue = ChaosVenue()
    venue.remote_positions = {"BTCUSDT": 2}
    venue.local_positions = {"BTCUSDT": 1}
    venue.reconnect()
    assert venue.local_positions == {"BTCUSDT": 2}
    assert venue.unsafe is False
