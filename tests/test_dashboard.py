import json
import threading
import urllib.request
from http.client import HTTPResponse
from pathlib import Path

from abdalghoniy.dashboard import _REQUEST_TIMES, _allow_request, make_status, safe_json


def test_dashboard_status_is_explicitly_paper_only():
    payload = make_status(Path('/root/abdalghoniy'))
    assert payload['mode'] == 'paper'
    assert payload['live_orders_enabled'] is False
    assert payload['kill_switch']['armed'] is None
    assert payload['kill_switch']['runtime_state_available'] is False


def test_safe_json_never_contains_secret_values():
    data = safe_json({'api_secret': 'secret-value', 'nested': {'token': 'abc'}})
    assert 'secret-value' not in json.dumps(data)
    assert data['api_secret'] == '[REDACTED]'


def test_public_request_limiter_rejects_burst_after_budget():
    client = 'test-client'
    _REQUEST_TIMES.pop(client, None)
    for _ in range(30):
        assert _allow_request(client) is True
    assert _allow_request(client) is False
    _REQUEST_TIMES.pop(client, None)


def test_status_verification_exposes_metadata_without_command_output(tmp_path):
    (tmp_path / '.dashboard_test_status').write_text(json.dumps({
        'status': 'passing',
        'evaluated_at': '2026-08-24T15:00:00+07:00',
        'commit': 'abc123',
        'checks': {'pytest': {'returncode': 0, 'output_tail': 'private diagnostic'}},
    }))
    verification = make_status(tmp_path)['verification']
    assert verification['commit'] == 'abc123'
    assert verification['checks']['pytest']['returncode'] == 0
    assert 'output_tail' not in json.dumps(verification)
