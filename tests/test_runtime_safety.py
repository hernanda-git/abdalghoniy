from abdalghoniy.runtime_safety import RuntimeSafetyState, RuntimeSafetyStore


def test_runtime_safety_state_is_atomic_and_readable(tmp_path):
    store=RuntimeSafetyStore(tmp_path/'runtime-safety.json')
    state=RuntimeSafetyState(True,False,None,10,20,False)
    store.write(state)
    assert store.read()==state


def test_corrupt_runtime_state_is_unavailable_not_safe():
    path=__import__('pathlib').Path('/tmp/runtime-safety-test.json'); path.write_text('{bad')
    assert RuntimeSafetyStore(path).read() is None
    path.unlink()
