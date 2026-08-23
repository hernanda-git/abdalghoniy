"""Conservative, public-only multi-exchange market-data pooling.

The pool is a failover router, not a rate-limit evasion mechanism. It performs one
request at a time, applies a per-exchange budget, caches at the caller, and falls
back only after a primary source fails or is unavailable.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class SourceResult:
    source: str
    rows: list[list[str]]
    method: str
    available: bool
    error: str | None = None


class ExchangeBudget:
    def __init__(self, *, max_requests: int, window_ms: int, clock_ms: Callable[[], int] | None = None):
        self.max_requests = max_requests
        self.window_ms = window_ms
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._calls: deque[int] = deque()

    def allow(self) -> bool:
        now = self.clock_ms()
        while self._calls and now - self._calls[0] >= self.window_ms:
            self._calls.popleft()
        if len(self._calls) >= self.max_requests:
            return False
        self._calls.append(now)
        return True

    @property
    def remaining(self) -> int:
        self.allow_cleanup()
        return max(0, self.max_requests - len(self._calls))

    def allow_cleanup(self) -> None:
        now = self.clock_ms()
        while self._calls and now - self._calls[0] >= self.window_ms:
            self._calls.popleft()


class SourceRouter:
    def __init__(self, sources: Iterable[tuple[str, Callable[[], Any]]]):
        self.sources = list(sources)

    def fetch(self) -> tuple[str, Any]:
        errors = []
        for name, callback in self.sources:
            try:
                value = callback()
                if value is not None:
                    return name, value
            except Exception as exc:
                errors.append(f"{name}:{type(exc).__name__}")
        raise RuntimeError("all market-data sources unavailable: " + ",".join(errors))


def normalise_bybit_kline(payload: dict) -> list[list[str]]:
    rows = payload.get("result", {}).get("list", [])
    return [list(map(str, row[:7])) for row in reversed(rows) if len(row) >= 6]


def _http_json(url: str, *, method: str = "GET", body: dict | None = None, timeout: float = 8.0) -> dict:
    encoded = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, method=method, data=encoded, headers={"User-Agent": "abdalghoniy-public-market/1.0", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


class PublicBybitClient:
    BASE_URL = "https://api.bybit.com"
    def __init__(self, *, transport: Callable[..., dict] | None = None, budget: ExchangeBudget | None = None):
        self.transport = transport or _http_json
        self.budget = budget or ExchangeBudget(max_requests=4, window_ms=1000)

    def daily(self, symbol: str = "BTCUSDT", limit: int = 365) -> SourceResult:
        if not self.budget.allow():
            return SourceResult("Bybit", [], "GET /v5/market/kline", False, "local_rate_budget_exhausted")
        query = urllib.parse.urlencode({"category": "linear", "symbol": symbol.upper(), "interval": "D", "limit": str(min(limit, 1000))})
        try:
            payload = self.transport(f"{self.BASE_URL}/v5/market/kline?{query}")
            if payload.get("retCode") != 0:
                raise RuntimeError(f"bybit_ret_{payload.get('retCode')}")
            return SourceResult("Bybit", normalise_bybit_kline(payload), "GET /v5/market/kline", True)
        except Exception as exc:
            return SourceResult("Bybit", [], "GET /v5/market/kline", False, type(exc).__name__)


class PublicHyperliquidClient:
    BASE_URL = "https://api.hyperliquid.xyz/info"
    def __init__(self, *, transport: Callable[..., dict] | None = None, budget: ExchangeBudget | None = None, clock_ms: Callable[[], int] | None = None):
        self.transport = transport or _http_json
        self.budget = budget or ExchangeBudget(max_requests=2, window_ms=1000)
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))

    def daily(self, coin: str = "BTC", limit: int = 365) -> SourceResult:
        if not self.budget.allow():
            return SourceResult("Hyperliquid", [], "POST /info candleSnapshot", False, "local_rate_budget_exhausted")
        end = self.clock_ms()
        body = {"type": "candleSnapshot", "req": {"coin": coin, "interval": "1d", "startTime": end - min(limit, 5000) * 86_400_000, "endTime": end}}
        try:
            payload = self.transport(self.BASE_URL, method="POST", body=body)
            rows = [[str(row.get("t")), str(row.get("o")), str(row.get("h")), str(row.get("l")), str(row.get("c")), str(row.get("v"))] for row in payload]
            return SourceResult("Hyperliquid", rows, "POST /info candleSnapshot", bool(rows), None if rows else "no_data")
        except Exception as exc:
            return SourceResult("Hyperliquid", [], "POST /info candleSnapshot", False, type(exc).__name__)


class PublicMexcClient:
    BASE_URL = "https://contract.mexc.com"
    def __init__(self, *, transport: Callable[..., dict] | None = None, budget: ExchangeBudget | None = None):
        self.transport = transport or _http_json
        self.budget = budget or ExchangeBudget(max_requests=2, window_ms=1000)

    def daily(self, symbol: str = "BTC_USDT", limit: int = 365) -> SourceResult:
        if not self.budget.allow():
            return SourceResult("MEXC", [], "GET /api/v1/contract/kline", False, "local_rate_budget_exhausted")
        query = urllib.parse.urlencode({"interval": "Day", "limit": str(min(limit, 500))})
        try:
            payload = self.transport(f"{self.BASE_URL}/api/v1/contract/kline/{symbol.upper()}?{query}")
            data = payload.get("data") or {}
            rows = []
            for values in zip(data.get("time", []), data.get("open", []), data.get("high", []), data.get("low", []), data.get("close", []), data.get("vol", [])):
                rows.append([str(value) for value in values])
            return SourceResult("MEXC", rows, "GET /api/v1/contract/kline", bool(rows), None if rows else "no_data")
        except Exception as exc:
            return SourceResult("MEXC", [], "GET /api/v1/contract/kline", False, type(exc).__name__)
