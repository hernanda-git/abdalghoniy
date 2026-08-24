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


def _interval_ms(interval: str) -> int:
    values = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1H": 3_600_000, "4H": 14_400_000, "1D": 86_400_000}
    try:
        return values[interval]
    except KeyError as exc:
        raise ValueError(f"unsupported interval for feature dataset: {interval}") from exc


def aggregate_cvd(timestamps: list[str], fills: Iterable[dict], interval: str) -> list[Decimal]:
    bucket_ms = _interval_ms(interval)
    starts = [int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000) for value in timestamps]
    start_set = set(starts)
    cvd = {start: Decimal("0") for start in starts}
    for fill in fills:
        timestamp = int(fill["ts"])
        bucket = timestamp // bucket_ms * bucket_ms
        if bucket not in start_set:
            continue
        size = Decimal(str(fill["size"]))
        side = str(fill["side"]).lower()
        if side == "buy":
            cvd[bucket] += size
        elif side == "sell":
            cvd[bucket] -= size
        else:
            raise ValueError(f"unknown public fill side: {fill['side']}")
    return [cvd[start] for start in starts]


def align_funding(timestamps: list[str], funding_rows: Iterable[dict]) -> list[Decimal]:
    events = sorted((int(row["fundingTime"]), Decimal(str(row["fundingRate"])) * Decimal("10000")) for row in funding_rows)
    result = []
    for value in timestamps:
        timestamp = int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        applicable = [rate for event_time, rate in events if event_time <= timestamp]
        result.append(applicable[-1] if applicable else Decimal("0"))
    return result


def _public_json(path: str, params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"https://api.bitget.com{path}?{query}", headers={"User-Agent": "abdalghoniy-paper/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("code") != "00000":
        raise RuntimeError(f"Bitget public request failed for {path}: {payload.get('code', 'NO_CODE')}")
    return payload


def fetch_public_fills(symbol: str, start_ms: int, end_ms: int, *, max_pages: int = 100) -> list[dict]:
    fills: dict[str, dict] = {}
    cursor = None
    for _ in range(max_pages):
        params = {"symbol": symbol, "productType": "SUSDT-FUTURES", "limit": "1000", "startTime": str(start_ms), "endTime": str(end_ms)}
        if cursor:
            params["idLessThan"] = cursor
        rows = _public_json("/api/v2/mix/market/fills-history", params).get("data", [])
        if not rows:
            break
        for row in rows:
            fills[str(row["tradeId"])] = row
        oldest = min(int(row["ts"]) for row in rows)
        cursor = str(rows[-1]["tradeId"])
        if oldest <= start_ms or len(rows) < 1000:
            break
    return sorted(fills.values(), key=lambda row: (int(row["ts"]), str(row["tradeId"])))


def fetch_historical_funding(symbol: str, *, page_size: int = 100) -> list[dict]:
    return _public_json("/api/v2/mix/market/history-fund-rate", {"symbol": symbol, "productType": "SUSDT-FUTURES", "pageSize": str(page_size)}).get("data", [])


def fetch_feature_complete_dataset(symbol: str, interval: str = "1m", limit: int = 100, output: Path | None = None) -> Path:
    venue_symbol = symbol.upper() if symbol.upper().startswith("S") and symbol.upper().endswith("SUSDT") else f"S{symbol.upper().removesuffix('USDT')}SUSDT"
    candle_path = fetch_demo_candles(symbol, interval, limit=limit, output=Path("/tmp") / f"{venue_symbol.lower()}_{interval}_candles.csv")
    rows = list(csv.DictReader(candle_path.read_text(encoding="utf-8").splitlines()))
    timestamps = [row["timestamp"] for row in rows]
    starts = [int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000) for value in timestamps]
    fills = fetch_public_fills(venue_symbol, min(starts), max(starts) + _interval_ms(interval))
    cvd = aggregate_cvd(timestamps, fills, interval)
    if not fills or all(value == 0 for value in cvd):
        raise RuntimeError("public fill data did not produce non-zero CVD; refusing incomplete dataset")
    funding = align_funding(timestamps, fetch_historical_funding(venue_symbol))
    target = output or Path("data") / f"{venue_symbol.lower()}_{interval}_feature_complete.csv"
    write_csv(target, [{**row, "cvd_change": str(cvd[index]), "funding_bps": str(funding[index])} for index, row in enumerate(rows)])
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
