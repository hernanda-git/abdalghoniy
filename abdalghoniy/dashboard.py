import json
import os
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = ROOT / 'web'


def safe_json(value: Any) -> Any:
    secret_words = ('secret', 'token', 'password', 'private_key', 'api_key')
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if any(w in k.lower() for w in secret_words) else safe_json(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_json(v) for v in value]
    return value


def make_status(root: Path = ROOT) -> dict:
    tests = 'unknown'
    marker = root / '.dashboard_test_status'
    if marker.exists():
        tests = marker.read_text().strip() or 'unknown'
    return {
        'service': 'ABDALGHONIY',
        'mode': 'paper',
        'live_orders_enabled': False,
        'timestamp_note': 'Server timestamps are UTC; UI displays Asia/Jakarta',
        'tests': tests,
        'kill_switch': {'armed': True, 'halted': False, 'partition_tolerant': True, 'protective_orders_preserved': True},
        'risk': {'hard_stop_required': True, 'daily_loss_breaker': True, 'max_leverage': 3, 'max_drawdown': '2%'},
        'validation': [
            {'gate': 'logic_review', 'status': 'implemented'},
            {'gate': 'purged_cv', 'status': 'implemented_not_passed'},
            {'gate': 'deflated_metric', 'status': 'not_passed'},
            {'gate': 'walk_forward', 'status': 'not_passed'},
            {'gate': 'shadow', 'status': 'implemented_no_live_stream'},
            {'gate': 'micro_live', 'status': 'blocked_no_credentials'},
        ],
        'strategies': {'counter_trend_scalp': 'paper-only', 'funding_carry': 'paper-only', 'mean_reversion': 'paper-only'},
        'reports': ['/reports/P0.md', '/reports/P1.md', '/reports/P2-P4.md', '/reports/REVIEW.md'],
    }


def market_snapshot() -> dict:
    # Demo-only public market data. The symbol is deliberately the SUSDT demo
    # instrument, never the live USDT-FUTURES product.
    url = 'https://api.bitget.com/api/v2/mix/market/tickers?productType=SUSDT-FUTURES'
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.load(response)
        rows = payload.get('data') or []
        row = next((item for item in rows if item.get('symbol') == 'SBTCSUSDT'), rows[0] if rows else None)
        if not row:
            return {'source': 'Bitget SUSDT-FUTURES public ticker', 'ok': False, 'error': 'NoDemoTicker'}
        return {'source': 'Bitget SUSDT-FUTURES public ticker', 'symbol': row.get('symbol'), 'price': row.get('lastPr'), 'ok': True}
    except Exception as exc:
        return {'source': 'Bitget SUSDT-FUTURES public ticker', 'ok': False, 'error': type(exc).__name__}


class Handler(BaseHTTPRequestHandler):
    server_version = 'ABDALGHONIY/0.1'

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == '/healthz':
            self._send(200, b'{"ok":true}', 'application/json')
        elif path == '/api/status':
            self._send(200, json.dumps(safe_json(make_status())).encode(), 'application/json')
        elif path == '/api/market':
            self._send(200, json.dumps(market_snapshot()).encode(), 'application/json')
        else:
            if path.startswith('/reports/'):
                target = ROOT / path.lstrip('/')
                allowed = ROOT / 'reports'
                if not target.exists() or not target.is_file() or allowed not in target.parents:
                    self._send(404, b'Not found', 'text/plain; charset=utf-8')
                    return
            else:
                target = WEB_ROOT / ('index.html' if path == '/' else path.lstrip('/'))
                if not target.exists() or not target.is_file() or WEB_ROOT not in target.parents:
                    self._send(404, b'Not found', 'text/plain; charset=utf-8')
                    return
            content_type = 'text/html; charset=utf-8' if target.suffix == '.html' else 'text/plain; charset=utf-8'
            self._send(200, target.read_bytes(), content_type)

    def log_message(self, fmt, *args):
        return


def serve(host: str = '127.0.0.1', port: int = 8787) -> None:
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == '__main__':
    serve(os.getenv('ABD_DASHBOARD_HOST', '127.0.0.1'), int(os.getenv('ABD_DASHBOARD_PORT', '8787')))
