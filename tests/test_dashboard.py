import json
import threading
import urllib.request
from http.client import HTTPResponse
from pathlib import Path

from abdalghoniy.dashboard import make_status, safe_json


def test_dashboard_status_is_explicitly_paper_only():
    payload = make_status(Path('/root/abdalghoniy'))
    assert payload['mode'] == 'paper'
    assert payload['live_orders_enabled'] is False
    assert payload['kill_switch']['armed'] is True


def test_safe_json_never_contains_secret_values():
    data = safe_json({'api_secret': 'secret-value', 'nested': {'token': 'abc'}})
    assert 'secret-value' not in json.dumps(data)
    assert data['api_secret'] == '[REDACTED]'
