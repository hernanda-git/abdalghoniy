from abdalghoniy.validation import GateResult, ValidationLadder


def test_fabricated_gate_details_do_not_authorize():
    ladder = ValidationLadder()
    gates = [GateResult(n, True, 'pass') for n in ladder.names]
    assert not ladder.authorize(gates)


def test_evidence_backed_gates_authorize_only_with_complete_metadata():
    ladder = ValidationLadder()
    gates = [GateResult(n, True, '{"dataset_hash":"abc123","evaluated_at":"2026-08-23T00:00:00Z","code_hash":"def456","metric":1}') for n in ladder.names]
    assert ladder.authorize(gates)
