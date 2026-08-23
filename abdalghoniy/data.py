import csv
import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .strategies import Candle


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
