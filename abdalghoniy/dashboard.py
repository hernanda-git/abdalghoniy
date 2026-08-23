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

from .analytics import DailyCandle, calendar_range, period_ranges, pivot_clusters, rsi, smc_events
from .liquidations import PublicLiquidationHeatmapClient
from .market_data import MarketDataCache, PublicBitgetMarketData
from .market_depth import OrderBookAggregator
from .multi_exchange import PublicBybitClient, PublicHyperliquidClient, PublicMexcClient, SourceResult, SourceRouter

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
        timestamp = int(row[0])
        if timestamp < 10_000_000_000:
            timestamp *= 1000
        rows.append(DailyCandle(datetime.fromtimestamp(timestamp / 1000, timezone.utc), row[1], row[2], row[3], row[4], row[5]))
    return rows


def _pooled_daily(symbol: str = "BTCUSDT") -> tuple[str, list[DailyCandle], list[dict]]:
    hyperliquid = PublicHyperliquidClient()
    bybit = PublicBybitClient()
    mexc = PublicMexcClient()
    bitget = PublicBitgetMarketData()
    attempts: list[dict] = []
    def attempt(name: str, callback):
        result = callback()
        attempts.append({"source": result.source, "available": result.available, "method": result.method, "error": result.error, "rows": len(result.rows)})
        if not result.available:
            raise RuntimeError(result.error or "unavailable")
        return result.rows
    def bitget_attempt():
        result = bitget.candles(symbol, granularity="1D", limit=365)
        return SourceResult("Bitget", result.data or [], "GET /api/v2/mix/market/candles", not result.metadata.unavailable, result.metadata.error)
    source, raw = SourceRouter([
        ("Hyperliquid", lambda: attempt("Hyperliquid", lambda: hyperliquid.daily(symbol.removesuffix("USDT")))),
        ("Bybit", lambda: attempt("Bybit", lambda: bybit.daily(symbol))),
        ("MEXC", lambda: attempt("MEXC", lambda: mexc.daily(symbol.replace("USDT", "_USDT")))),
        ("Bitget", lambda: attempt("Bitget", bitget_attempt)),
    ]).fetch()
    return source, _candle_rows(raw), attempts


def _result_payload(result: Any) -> dict:
    return {"available": result.available, "value": result.value, "reason": result.reason}


def intelligence_snapshot(symbol: str = "BTCUSDT") -> dict:
    """Return one cached, read-only intelligence snapshot for the demo instrument."""
    with _INTELLIGENCE_LOCK:
        def fetch() -> dict:
            source, rows, attempts = _pooled_daily(symbol)
            weekly = period_ranges(rows, "week") if rows else []
            monthly = period_ranges(rows, "month") if rows else []
            yearly = calendar_range(rows, "year") if rows else None
            pivots = pivot_clusters(rows, left=2, right=2) if rows else None
            rsi_result = rsi(rows, period=14) if rows else None
            smc = smc_events(rows, left=2, right=2) if rows else None
            depth_result = PublicBitgetMarketData().depth(symbol, limit=20)
            order_book = OrderBookAggregator.from_bitget(depth_result.data or {}) if depth_result.data else {"status": "unavailable", "error": depth_result.metadata.error or "no_depth"}
            if hasattr(order_book, "__dict__"):
                order_book = dict(order_book.__dict__)
            updated_at = int(rows[-1].timestamp.timestamp() * 1000) if rows else None
            return {
                "symbol": getattr(PublicBitgetMarketData, "venue_symbol", lambda value: value)(symbol),
                "ranges": {"weekly": [r.__dict__ for r in weekly], "monthly": [r.__dict__ for r in monthly], "yearly": _result_payload(yearly) if yearly else {"available": False, "value": None, "reason": "no daily candles"}, "period_semantics": "observed candles grouped by Monday-Sunday week, calendar month, and calendar year"},
                "support_resistance": _result_payload(pivots) if pivots else {"available": False, "value": [], "reason": "no daily candles"},
                "rsi": _result_payload(rsi_result) if rsi_result else {"available": False, "value": None, "reason": "no daily candles"},
                "smc": _result_payload(smc) if smc else {"available": False, "value": [], "reason": "no daily candles"},
                "order_book": order_book,
                "liquidations": dict(PublicLiquidationHeatmapClient().fetch(symbol).__dict__),
                "freshness": {"updated_at_ms": updated_at, "freshness_ms": None, "stale": False, "source": source, "method": "rate-budgeted sequential source failover"},
                "source_attempts": attempts,
                "rate_limit": {"policy": "one sequential request per source per refresh; local per-exchange budgets; no credentialed calls"},
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
