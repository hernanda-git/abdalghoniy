import json
import os
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from dataclasses import asdict, is_dataclass
from datetime import datetime, date, timezone
from decimal import Decimal
from threading import Lock

from .analytics import DailyCandle, period_ranges, pivot_clusters, rsi, smc_events
from .liquidations import PublicLiquidationHeatmapClient
from .market_data import MarketDataCache, PublicBitgetMarketData
from .market_depth import OrderBookAggregator

ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = ROOT / 'web'


def safe_json(value: Any) -> Any:
    secret_words = ('secret', 'token', 'password', 'private_key', 'api_key')
    if is_dataclass(value):
        return safe_json(asdict(value))
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if any(w in k.lower() for w in secret_words) else safe_json(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_json(v) for v in value]
    if isinstance(value, tuple):
        return [safe_json(v) for v in value]
    if isinstance(value, (Decimal, datetime, date)):
        return str(value)
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
        return {'source': 'Bitget public · SUSDT-FUTURES', 'symbol': row.get('symbol'), 'price': row.get('lastPr'), 'change24h': row.get('change24h'), 'high24h': row.get('high24h'), 'low24h': row.get('low24h'), 'ts': row.get('ts'), 'ok': True}
    except Exception as exc:
        return {'source': 'Bitget SUSDT-FUTURES public ticker', 'ok': False, 'error': type(exc).__name__}


_INTELLIGENCE_CACHE = MarketDataCache()
_INTELLIGENCE_LOCK = Lock()


def _candle_rows(raw: list) -> list[DailyCandle]:
    rows = []
    for row in raw:
        if len(row) < 6:
            continue
        rows.append(DailyCandle(datetime.fromtimestamp(int(row[0]) / 1000, timezone.utc), row[1], row[2], row[3], row[4], row[5]))
    return rows


def _result_payload(result: Any) -> dict:
    return {"available": result.available, "value": result.value, "reason": result.reason}


def intelligence_snapshot(symbol: str = "BTCUSDT") -> dict:
    """Return one cached, read-only intelligence snapshot for the demo instrument."""
    with _INTELLIGENCE_LOCK:
        def fetch() -> dict:
            client = PublicBitgetMarketData()
            candles_result = client.candles(symbol, granularity="1D", limit=100)
            metadata = candles_result.metadata
            rows = _candle_rows(candles_result.data or []) if candles_result.data else []
            weekly = period_ranges(rows, "week") if rows else []
            monthly = period_ranges(rows, "month") if rows else []
            pivots = pivot_clusters(rows, left=2, right=2) if rows else None
            rsi_result = rsi(rows, period=14) if rows else None
            smc = smc_events(rows, left=2, right=2) if rows else None
            depth_result = client.depth(symbol, limit=20)
            order_book = OrderBookAggregator.from_bitget(depth_result.data or {}) if depth_result.data else {"status": "unavailable", "error": depth_result.metadata.error or "no_depth"}
            if hasattr(order_book, "__dict__"):
                order_book = dict(order_book.__dict__)
            return {
                "symbol": getattr(client, "venue_symbol", lambda value: value)(symbol),
                "ranges": {"weekly": [r.__dict__ for r in weekly], "monthly": [r.__dict__ for r in monthly], "period_semantics": "observed candles grouped by Monday-Sunday week and calendar month"},
                "rsi": _result_payload(rsi_result) if rsi_result else {"available": False, "value": None, "reason": "no daily candles"},
                "support_resistance": _result_payload(pivots) if pivots else {"available": False, "value": [], "reason": "no daily candles"},
                "smc": _result_payload(smc) if smc else {"available": False, "value": [], "reason": "no daily candles"},
                "order_book": order_book,
                "liquidations": dict(PublicLiquidationHeatmapClient().fetch(symbol).__dict__),
                "freshness": {"updated_at_ms": metadata.updated_at_ms, "freshness_ms": metadata.freshness_ms, "stale": metadata.stale, "source": metadata.source, "method": metadata.method},
                "rate_limit": metadata.rate_limit,
            }
        return _INTELLIGENCE_CACHE.get_or_fetch(f"intelligence:{symbol}", fetch, ttl_ms=5000)


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
        elif path == '/api/intelligence':
            self._send(200, json.dumps(safe_json(intelligence_snapshot())).encode(), 'application/json')
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
            content_type = {
                '.html': 'text/html; charset=utf-8',
                '.js': 'application/javascript; charset=utf-8',
                '.css': 'text/css; charset=utf-8',
                '.svg': 'image/svg+xml',
                '.json': 'application/json; charset=utf-8',
            }.get(target.suffix, 'text/plain; charset=utf-8')
            self._send(200, target.read_bytes(), content_type)

    def log_message(self, fmt, *args):
        return


def serve(host: str = '127.0.0.1', port: int = 8787) -> None:
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == '__main__':
    serve(os.getenv('ABD_DASHBOARD_HOST', '127.0.0.1'), int(os.getenv('ABD_DASHBOARD_PORT', '8787')))
