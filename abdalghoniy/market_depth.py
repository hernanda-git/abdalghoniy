"""Read-only Bitget SUSDT demo order-book aggregation."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .multi_exchange import EndpointGuard, GLOBAL_ENDPOINT_GUARD


class ProductTypeError(ValueError):
    """Raised when a live USDT-FUTURES product is requested."""


@dataclass(frozen=True)
class OrderBookSnapshot:
    status: str
    best_bid: float | None = None
    best_ask: float | None = None
    spread: float | None = None
    bid_depth: float | None = None
    ask_depth: float | None = None
    imbalance: float | None = None
    timestamp_ms: int | None = None
    error: str | None = None


class OrderBookAggregator:
    @classmethod
    def from_bitget(cls, payload: dict, depth_levels: int = 10) -> OrderBookSnapshot:
        bids = cls._levels(payload.get("bids"), depth_levels)
        asks = cls._levels(payload.get("asks"), depth_levels)
        if not bids or not asks:
            return OrderBookSnapshot(status="unavailable", error="missing_order_book_side")
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        if best_bid >= best_ask:
            return OrderBookSnapshot(status="unavailable", error="crossed_order_book")
        bid_depth = sum(size for _, size in bids)
        ask_depth = sum(size for _, size in asks)
        total = bid_depth + ask_depth
        return OrderBookSnapshot(
            status="ok",
            best_bid=best_bid,
            best_ask=best_ask,
            spread=best_ask - best_bid,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            imbalance=(bid_depth - ask_depth) / total if total else None,
            timestamp_ms=int(payload["ts"]) if payload.get("ts") is not None else None,
        )

    @staticmethod
    def _levels(raw: object, depth_levels: int) -> list[tuple[float, float]]:
        if not isinstance(raw, list) or depth_levels <= 0:
            return []
        levels = []
        for row in raw[:depth_levels]:
            try:
                price, size = float(row[0]), float(row[1])
            except (IndexError, TypeError, ValueError):
                continue
            if price > 0 and size >= 0:
                levels.append((price, size))
        return levels


class PublicOrderBookClient:
    """Public, unauthenticated depth client. It has no order methods."""

    ENDPOINT = "/api/v2/mix/market/merge-depth"
    RATE_LIMIT_REQUESTS_PER_SECOND = 20

    def __init__(self, *, product_type: str = "SUSDT-FUTURES", base_url: str = "https://api.bitget.com", transport: Callable | None = None, endpoint_guard: EndpointGuard | None = None):
        if product_type != "SUSDT-FUTURES":
            raise ProductTypeError("ABDALGHONIY permits only SUSDT-FUTURES")
        self.product_type = product_type
        self.base_url = base_url.rstrip("/")
        self.transport = transport or self._urlopen_transport
        self.endpoint_guard = endpoint_guard or GLOBAL_ENDPOINT_GUARD

    @staticmethod
    def venue_symbol(symbol: str) -> str:
        symbol = symbol.upper()
        if symbol.startswith("S") and symbol.endswith("SUSDT"):
            return symbol
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        return f"S{base}SUSDT"

    @staticmethod
    def _urlopen_transport(method: str, url: str, headers=None, body=None):
        request = urllib.request.Request(url, method=method, headers=headers or {})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def fetch(self, symbol: str, *, limit: int = 20) -> OrderBookSnapshot:
        if not 1 <= limit <= 100:
            return OrderBookSnapshot(status="unavailable", error="invalid_limit")
        endpoint = f"Bitget:{self.ENDPOINT}"
        decision = self.endpoint_guard.check(endpoint)
        if not decision.allowed:
            return OrderBookSnapshot(status="unavailable", error=f"{decision.reason}:retry_after_{decision.retry_after_ms}ms")
        query = urllib.parse.urlencode({"symbol": self.venue_symbol(symbol), "productType": self.product_type, "limit": str(limit)})
        url = f"{self.base_url}{self.ENDPOINT}?{query}"
        try:
            payload = self.transport("GET", url, headers={}, body=None)
            if payload.get("code") != "00000":
                error = f"bitget_code_{payload.get('code')}"
                self.endpoint_guard.record_error(endpoint, error)
                return OrderBookSnapshot(status="unavailable", error=error)
            return OrderBookAggregator.from_bitget(payload.get("data") or {})
        except (OSError, TimeoutError, ValueError, TypeError, KeyError) as exc:
            self.endpoint_guard.record_error(endpoint, str(exc))
            return OrderBookSnapshot(status="unavailable", error=str(exc) or type(exc).__name__.lower())
