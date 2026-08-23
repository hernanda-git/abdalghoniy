import json
import time
from pathlib import Path


class ShadowRunner:
    """Zero-order market shadow processor with fail-closed freshness checks."""

    def __init__(self, symbol: str, event_path: Path | None = None, *, max_age_s: int = 15, max_gap_s: int = 60, now=None):
        self.symbol = symbol
        self.event_path = Path(event_path) if event_path else None
        self.max_age_s = max_age_s
        self.max_gap_s = max_gap_s
        self.now = now or time.time
        self.last_timestamp = None
        self.unsafe_reason = None

    def _persist(self, event: dict) -> None:
        if self.event_path:
            self.event_path.parent.mkdir(parents=True, exist_ok=True)
            with self.event_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")

    def process(self, tick: dict) -> dict:
        timestamp = float(tick["timestamp"])
        price = float(tick["price"])
        if price <= 0:
            status, reason = "unsafe", "invalid_price"
        elif self.now() - timestamp > self.max_age_s:
            status, reason = "stale", "market_data_stale"
        elif self.last_timestamp is not None and timestamp - self.last_timestamp > self.max_gap_s:
            status, reason = "gap", "market_data_gap"
        else:
            status, reason = "ok", None
        self.last_timestamp = timestamp
        self.unsafe_reason = reason
        result = {"symbol": self.symbol, "timestamp": timestamp, "price": price, "status": status, "reason": reason, "would_order": False, "source": "stream"}
        self._persist(result)
        return result

    def poll(self, stream, rest_fallback) -> dict:
        try:
            tick = stream()
            result = self.process(tick)
        except Exception as exc:
            tick = rest_fallback()
            result = self.process(tick)
            result["source"] = "rest_fallback"
            result["stream_error"] = type(exc).__name__
        return result
