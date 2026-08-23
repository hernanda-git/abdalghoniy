import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


class LiveDemoShadow:
    """Public Bitget demo candle poller with no credentials and no order path."""

    def __init__(self, symbol: str, event_path: Path, *, fetcher=None, now_ms=None, max_age_ms: int = 120_000):
        self.symbol = symbol.upper()
        base = self.symbol[:-4] if self.symbol.endswith("USDT") else self.symbol
        self.venue_symbol = self.symbol if self.symbol.startswith("S") and self.symbol.endswith("SUSDT") else f"S{base}SUSDT"
        self.event_path = Path(event_path)
        self.fetcher = fetcher or self._fetch
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        self.max_age_ms = max_age_ms
        self.last_ts = None

    @staticmethod
    def _fetch(symbol, interval, limit):
        query = urllib.parse.urlencode({"symbol": symbol, "productType": "SUSDT-FUTURES", "granularity": interval, "limit": str(limit)})
        request = urllib.request.Request(f"https://api.bitget.com/api/v2/mix/market/candles?{query}", headers={"User-Agent": "abdalghoniy-shadow/0.1"})
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
        if payload.get("code") != "00000":
            raise RuntimeError(f"Bitget demo candle fetch failed: {payload.get('code')}")
        return payload.get("data") or []

    def _write(self, event):
        self.event_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def poll_once(self):
        rows = self.fetcher(self.venue_symbol, "1m", 2)
        if not rows:
            result = {"symbol": self.symbol, "venue_symbol": self.venue_symbol, "status": "no_data", "would_order": False}
            self._write(result)
            return result
        row = max(rows, key=lambda item: int(item[0]))
        timestamp = int(row[0])
        if self.last_ts == timestamp:
            status = "duplicate"
        elif self.now_ms() - timestamp > self.max_age_ms:
            status = "stale"
        else:
            status = "ok"
        self.last_ts = timestamp
        result = {
            "symbol": self.symbol,
            "venue_symbol": self.venue_symbol,
            "timestamp_ms": timestamp,
            "status": status,
            "price": row[4],
            "volume": row[5],
            "cvd_change": None,
            "funding_bps": None,
            "would_order": False,
            "raw": row,
        }
        self._write(result)
        return result
