import json
import os
import re
import shutil
import sqlite3
import time
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
            {'gate': 'logic_review', 'status': 'implemented', 'reason': 'paper-only safety and code review path exists'},
            {'gate': 'purged_cv', 'status': 'blocked_insufficient_trades', 'reason': 'current replay has 0 realized trades; purged cross-validation cannot be promoted'},
            {'gate': 'deflated_metric', 'status': 'blocked_insufficient_trials', 'reason': 'no valid realized trade sample across multiple configurations'},
            {'gate': 'walk_forward', 'status': 'blocked_insufficient_out_of_sample', 'reason': 'current dataset has 100 candles and no realized trades'},
            {'gate': 'shadow', 'status': 'implemented_live_public_readonly', 'reason': 'public multi-exchange data path verified without orders'},
            {'gate': 'micro_live', 'status': 'blocked_paper_only_no_credentials', 'reason': 'live orders and credentialed paths are intentionally disabled'},
        ],
        'strategies': {'counter_trend_scalp': 'paper-only', 'funding_carry': 'paper-only', 'mean_reversion': 'paper-only'},
        'reports': ['/reports/P0.md', '/reports/P1.md', '/reports/P2-P4.md', '/reports/REVIEW.md'],
    }


_HEALTH_CACHE = MarketDataCache()


def _read_meminfo() -> dict[str, int]:
    values = {}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            key, raw = line.split(':', 1)
            values[key] = int(raw.strip().split()[0]) * 1024
    except (OSError, ValueError):
        return {}
    return values


def _database_inventory() -> list[dict]:
    output = []
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.suffix not in {'.db', '.sqlite', '.sqlite3'}:
            continue
        entry = {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'tables': []}
        try:
            with sqlite3.connect(path) as db:
                tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                for table in tables:
                    count = db.execute(f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"').fetchone()[0]
                    entry['tables'].append({'name': table, 'rows': count})
        except (OSError, sqlite3.Error) as exc:
            entry['error'] = type(exc).__name__
        output.append(entry)
    return output


def _project_size() -> int:
    total = 0
    for path in ROOT.rglob('*'):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def health_snapshot() -> dict:
    def collect() -> dict:
        disk = shutil.disk_usage(ROOT)
        mem = _read_meminfo()
        rss = 0
        try:
            for line in Path('/proc/self/status').read_text().splitlines():
                if line.startswith('VmRSS:'):
                    rss = int(line.split()[1]) * 1024
                    break
        except (OSError, ValueError):
            pass
        try:
            load = list(os.getloadavg())
        except OSError:
            load = []
        return {
            'project': {'path': str(ROOT), 'bytes': _project_size()},
            'databases': _database_inventory(),
            'process': {'rss_bytes': rss, 'pid': os.getpid()},
            'host': {'cpu_count': os.cpu_count(), 'uptime_seconds': int(float(Path('/proc/uptime').read_text().split()[0])) if Path('/proc/uptime').exists() else None, 'load_1m': load[0] if load else None, 'load_5m': load[1] if len(load) > 1 else None, 'load_15m': load[2] if len(load) > 2 else None, 'memory_total_bytes': mem.get('MemTotal'), 'memory_available_bytes': mem.get('MemAvailable'), 'swap_total_bytes': mem.get('SwapTotal'), 'swap_free_bytes': mem.get('SwapFree')},
            'disk': {'mount': str(ROOT), 'total_bytes': disk.total, 'used_bytes': disk.total - disk.free, 'free_bytes': disk.free},
            'safety': {'mode': 'paper', 'live_orders_enabled': False, 'credentialed_requests': False},
            'generated_at_ms': int(time.time() * 1000),
        }
    return _HEALTH_CACHE.get_or_fetch('health', collect, ttl_ms=10000)


def public_health_snapshot() -> dict:
    """Return only safe liveness metadata for the unauthenticated dashboard."""
    return {"status": "ok", "mode": "paper", "data_plane": "rest"}


_MARKET_CACHE = MarketDataCache()


def market_snapshot() -> dict:
    return _MARKET_CACHE.get_or_fetch("bitget:ticker:SBTCSUSDT", _market_snapshot_uncached, ttl_ms=5000)


def _market_snapshot_uncached() -> dict:
    result = PublicBitgetMarketData().ticker("BTCUSDT")
    if result.metadata.unavailable or not result.data:
        return {'source': 'Bitget SUSDT-FUTURES public ticker', 'ok': False, 'error': result.metadata.error or 'Unavailable', 'rate_limit': result.metadata.rate_limit}
    row = result.data
    return {'source': 'Bitget public · SUSDT-FUTURES', 'symbol': row.get('symbol'), 'price': row.get('lastPr'), 'change24h': row.get('change24h'), 'high24h': row.get('high24h'), 'low24h': row.get('low24h'), 'ts': row.get('ts'), 'ok': True, 'rate_limit': result.metadata.rate_limit}

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
            now_ms = int(time.time() * 1000)
            historical_freshness_ms = max(0, now_ms - updated_at) if updated_at is not None else None
            order_book_timestamp = order_book.get("timestamp_ms") if isinstance(order_book, dict) else None
            order_book_freshness_ms = max(0, now_ms - int(order_book_timestamp)) if order_book_timestamp is not None else None
            return {
                "symbol": getattr(PublicBitgetMarketData, "venue_symbol", lambda value: value)(symbol),
                "ranges": {"weekly": [r.__dict__ for r in weekly], "monthly": [r.__dict__ for r in monthly], "yearly": _result_payload(yearly) if yearly else {"available": False, "value": None, "reason": "no daily candles"}, "period_semantics": "observed candles grouped by Monday-Sunday week, calendar month, and calendar year"},
                "support_resistance": _result_payload(pivots) if pivots else {"available": False, "value": [], "reason": "no daily candles"},
                "rsi": _result_payload(rsi_result) if rsi_result else {"available": False, "value": None, "reason": "no daily candles"},
                "smc": _result_payload(smc) if smc else {"available": False, "value": [], "reason": "no daily candles"},
                "order_book": order_book,
                "liquidations": dict(PublicLiquidationHeatmapClient().fetch(symbol).__dict__),
                "freshness": {"updated_at_ms": updated_at, "freshness_ms": historical_freshness_ms, "stale": historical_freshness_ms is None or historical_freshness_ms > 36 * 60 * 60 * 1000, "source": source, "method": "rate-budgeted sequential source failover", "kind": "historical_daily"},
                "order_book_freshness": {"updated_at_ms": order_book_timestamp, "freshness_ms": order_book_freshness_ms, "stale": order_book_freshness_ms is None or order_book_freshness_ms > 60 * 1000, "kind": "order_book"},
                "source_attempts": attempts,
                "rate_limit": {"policy": "one sequential request per source per refresh; local per-exchange budgets; no credentialed calls"},
            }
        return _INTELLIGENCE_CACHE.get_or_fetch(f"intelligence:{symbol}", fetch, ttl_ms=15000)


class Handler(BaseHTTPRequestHandler):
    server_version = 'ABDALGHONIY/0.1'

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == '/healthz':
            self._send(200, b'{"ok":true}', 'application/json')
        elif path == '/api/status':
            self._send(200, json.dumps(safe_json(make_status())).encode(), 'application/json')
        elif path == '/api/health':
            self._send(200, json.dumps(public_health_snapshot()).encode(), 'application/json')
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

    def _method_not_allowed(self) -> None:
        self.send_response(405)
        self.send_header('Allow', 'GET')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_HEAD(self) -> None:
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:
        self._method_not_allowed()

    def do_POST(self) -> None:
        self._method_not_allowed()

    def do_PUT(self) -> None:
        self._method_not_allowed()

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        self._method_not_allowed()

    def log_message(self, fmt, *args):
        return


def serve(host: str = '127.0.0.1', port: int = 8787) -> None:
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == '__main__':
    serve(os.getenv('ABD_DASHBOARD_HOST', '127.0.0.1'), int(os.getenv('ABD_DASHBOARD_PORT', '8787')))
