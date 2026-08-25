from abdalghoniy.safety import KillSwitch, OrderBook, OrderIntent
from abdalghoniy.runtime_safety import RuntimeSafetyStore, RuntimeSafetyState
import pytest, pathlib


def test_kill_switch_preserves_reduce_only_protective_orders_on_partition():
    book = OrderBook([
        OrderIntent('stop1', 'BTCUSDT', reduce_only=True, protective=True),
        OrderIntent('entry1', 'BTCUSDT', reduce_only=False, protective=False),
    ])
    ks = KillSwitch(book)
    ks.arm()
    ks.partition_detected('network partition simulated')
    assert ks.is_halted() is True
    # Protective reduce-only order must survive the halt.
    assert book.is_cancelled('stop1') is False
    # Non-protective entry must be cancelled.
    assert book.is_cancelled('entry1') is True


def test_kill_switch_refuses_trades_when_unarmed_or_halted():
    book = OrderBook([OrderIntent('stop1', 'BTCUSDT', reduce_only=True, protective=True)])
    ks = KillSwitch(book)
    from abdalghoniy.risk import HardStop
    stop = HardStop.for_entry('long', 100, 2)
    with pytest.raises(PermissionError):
        ks.authorize(OrderIntent('x', 'BTCUSDT'), stop, validation_complete=True)
    ks.arm()
    ks.partition_detected('partition')
    with pytest.raises(PermissionError):
        ks.authorize(OrderIntent('x', 'BTCUSDT'), stop, validation_complete=True)


def test_runtime_safety_missing_state_defaults_to_unsafe_no_trade(tmp_path):
    store = RuntimeSafetyStore(tmp_path / 'missing.json')
    assert store.read() is None  # missing state is NOT a green light


def test_runtime_safety_corrupt_state_is_unavailable(tmp_path):
    p = tmp_path / 'corrupt.json'
    p.write_text('{not-json')
    assert RuntimeSafetyStore(p).read() is None


def test_runtime_safety_armed_state_is_observable(tmp_path):
    store = RuntimeSafetyStore(tmp_path / 'rt.json')
    store.write(RuntimeSafetyState(True, False, None, 0, None, False))
    state = store.read()
    assert state.armed is True and state.halted is False
