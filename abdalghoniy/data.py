import csv
import hashlib
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .strategies import Candle
from .market_data import PublicBitgetMarketData


@dataclass(frozen=True)
class MarketDataset:
    candles: list[Candle]
    cvd_changes: list[Decimal]
    funding_bps: list[Decimal]
    timestamps: list[str]
    sha256: str


def load_csv(path: Path) -> MarketDataset:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    required = {"open", "high", "low", "close", "volume"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("dataset must contain open, high, low, close, and volume columns")
    candles: list[Candle] = []
    cvd: list[Decimal] = []
    funding: list[Decimal] = []
    timestamps: list[str] = []
    for row in rows:
        candles.append(Candle(row["open"], row["high"], row["low"], row["close"], row["volume"]))
        cvd.append(Decimal(str(row.get("cvd_change") or "0")))
        funding.append(Decimal(str(row.get("funding_bps") or "0")))
        timestamps.append(str(row.get("timestamp") or ""))
    return MarketDataset(candles, cvd, funding, timestamps, digest)


def fetch_demo_candles(symbol: str, interval: str, limit: int = 100, output: Path | None = None) -> Path:
    """Fetch public Bitget demo candles only. This function has no auth or order path."""
    if symbol.upper().startswith("S") and symbol.upper().endswith("SUSDT"):
        venue_symbol = symbol.upper()
    else:
        base = symbol.upper()[:-4] if symbol.upper().endswith("USDT") else symbol.upper()
        venue_symbol = f"S{base}SUSDT"
    granularity = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "1H": "1H", "4H": "4H", "1D": "1D"}.get(interval)
    if granularity is None:
        raise ValueError("unsupported interval for Bitget public candles")
    query = urllib.parse.urlencode({"symbol": venue_symbol, "productType": "SUSDT-FUTURES", "granularity": granularity, "limit": str(limit)})
    request = urllib.request.Request(f"https://api.bitget.com/api/v2/mix/market/candles?{query}", headers={"User-Agent": "abdalghoniy-paper/0.1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if payload.get("code") != "00000" or not payload.get("data"):
        raise RuntimeError(f"Bitget demo candle fetch failed: {payload.get('code', 'NO_DATA')}")
    rows = sorted(payload["data"], key=lambda row: int(row[0]))
    target = output or Path("data") / f"{venue_symbol.lower()}_{interval}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume", "cvd_change", "funding_bps"])
        writer.writeheader()
        for timestamp, open_, high, low, close, volume, *_ in rows:
            writer.writerow({
                "timestamp": datetime.fromtimestamp(int(timestamp) / 1000, timezone.utc).isoformat(),
                "open": open_, "high": high, "low": low, "close": close, "volume": volume,
                "cvd_change": "", "funding_bps": "",
            })
    return target


def write_csv(path: Path, rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError("cannot write an empty dataset")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["timestamp", "open", "high", "low", "close", "volume", "cvd_change", "funding_bps"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
