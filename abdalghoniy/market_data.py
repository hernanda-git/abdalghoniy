"""Shared, read-only market-data access for the paper dashboard.

This module is deliberately limited to Bitget's public SUSDT-FUTURES demo
product. It contains no credentials and no order/account endpoints.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


PUBLIC_RATE_LIMIT = {"limit": 20, "window": "1s", "scope": "public"}


@dataclass(frozen=True)
class MarketDataMetadata:
    source: str
    method: str
    updated_at_ms: int | None
    freshness_ms: int | None
    stale: bool
    rate_limit: dict[str, Any]
    unavailable: bool = False
    error: str | None = None


@dataclass(frozen=True)
class MarketDataResult:
    data: Any
    metadata: MarketDataMetadata


class MarketDataCache:
    """Small in-process TTL cache shared by all public market-data readers."""

    def __init__(self, *, clock_ms: Callable[[], int] | None = None) -> None:
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._values: dict[str, tuple[int, Any]] = {}

    def get_or_fetch(self, key: str, fetcher: Callable[[], Any], *, ttl_ms: int) -> Any:
        now = self.clock_ms()
        cached = self._values.get(key)
        if cached and now - cached[0] < ttl_ms:
            return cached[1]
        value = fetcher()
        self._values[key] = (now, value)
        return value

    def clear(self) -> None:
        self._values.clear()


@dataclass
class _Job:
    callback: Callable[[], Any]
    interval_ms: int
    next_run_ms: int


class MarketDataScheduler:
    """Deterministic scheduler; `run_due` is also convenient for HTTP servers."""

    def __init__(self, *, clock_ms: Callable[[], int] | None = None) -> None:
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.jobs: dict[str, _Job] = {}
        self.last_results: dict[str, Any] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def register(self, name: str, callback: Callable[[], Any], *, interval_ms: int) -> None:
        if interval_ms <= 0:
            raise ValueError("interval_ms must be positive")
        self.jobs[name] = _Job(callback, interval_ms, self.clock_ms())

    def run_due(self) -> dict[str, Any]:
        now = self.clock_ms()
        results: dict[str, Any] = {}
        for name, job in self.jobs.items():
            if now < job.next_run_ms:
                continue
            try:
                result = job.callback()
            except Exception as exc:  # scheduler remains alive; caller gets structured failure
                result = exc
            self.last_results[name] = result
            results[name] = result
            job.next_run_ms = now + job.interval_ms
        return results

    def start(self, *, poll_ms: int = 100) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def loop() -> None:
            while not self._stop.is_set():
                self.run_due()
                self._stop.wait(poll_ms / 1000)

        self._thread = threading.Thread(target=loop, name="market-data-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


class PublicBitgetMarketData:
    """Bitget V2 public market endpoints, restricted to SUSDT-FUTURES."""

    BASE_URL = "https://api.bitget.com"
    PRODUCT_TYPE = "SUSDT-FUTURES"
    _ENDPOINTS = {
        "ticker": "/api/v2/mix/market/ticker",
        "candles": "/api/v2/mix/market/candles",
        "depth": "/api/v2/mix/market/orderbook",
    }

    def __init__(self, *, transport: Callable | None = None, base_url: str = BASE_URL,
                 clock_ms: Callable[[], int] | None = None, stale_after_ms: int = 120_000) -> None:
        self.transport = transport or self._urlopen_transport
        self.base_url = base_url.rstrip("/")
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.stale_after_ms = stale_after_ms

    @staticmethod
    def venue_symbol(symbol: str) -> str:
        value = symbol.upper()
        if value.startswith("S") and value.endswith("SUSDT"):
            return value
        base = value[:-4] if value.endswith("USDT") else value
        return f"S{base}SUSDT"

    @staticmethod
    def _urlopen_transport(method: str, url: str, headers=None, body=None) -> dict:
        request = urllib.request.Request(url, method=method, headers=headers or {})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def _request(self, kind: str, symbol: str, params: dict[str, str]) -> MarketDataResult:
        path = self._ENDPOINTS[kind]
        query = urllib.parse.urlencode(params)
        method = f"GET {path}"
        try:
            payload = self.transport("GET", f"{self.base_url}{path}?{query}", headers={}, body=None)
            if payload.get("code") != "00000":
                raise RuntimeError(f"Bitget code {payload.get('code', 'unknown')}")
            raw = payload.get("data")
            if kind == "ticker":
                data = (raw or [None])[0]
                if data is None:
                    raise RuntimeError("NoData")
                updated = int(data["ts"]) if data.get("ts") else self.clock_ms()
            elif kind == "candles":
                data = raw or []
                if not data:
                    raise RuntimeError("NoData")
                updated = max((int(row[0]) for row in data), default=None)
            else:
                data = raw or {}
                if not data:
                    raise RuntimeError("NoData")
                updated = int(data["ts"]) if data.get("ts") else self.clock_ms()
            freshness = self.clock_ms() - updated if updated is not None else None
            stale_after = self.stale_after_ms
            if kind == "candles" and params.get("granularity", "").upper() == "1D":
                stale_after = max(stale_after, 172_800_000)
            return MarketDataResult(data, MarketDataMetadata("Bitget", method, updated, freshness,
                freshness is None or freshness > stale_after, dict(PUBLIC_RATE_LIMIT)))
        except Exception as exc:
            return MarketDataResult(None, MarketDataMetadata("Bitget", method, None, None, True,
                dict(PUBLIC_RATE_LIMIT), unavailable=True, error=type(exc).__name__))

    def ticker(self, symbol: str) -> MarketDataResult:
        return self._request("ticker", symbol, {"productType": self.PRODUCT_TYPE, "symbol": self.venue_symbol(symbol)})

    def candles(self, symbol: str, *, granularity: str = "1m", limit: int = 100) -> MarketDataResult:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        return self._request("candles", symbol, {"productType": self.PRODUCT_TYPE, "symbol": self.venue_symbol(symbol), "granularity": granularity, "limit": str(limit)})

    def depth(self, symbol: str, *, limit: int = 20) -> MarketDataResult:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return self._request("depth", symbol, {"productType": self.PRODUCT_TYPE, "symbol": self.venue_symbol(symbol), "limit": str(limit)})
