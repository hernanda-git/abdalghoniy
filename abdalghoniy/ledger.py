import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


class DurableLedger:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS equity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            equity TEXT NOT NULL,
            drawdown TEXT NOT NULL
        );
        """)
        self.db.commit()

    def record_trade(self, trade: dict) -> None:
        self.db.execute("INSERT INTO trades(recorded_at,payload) VALUES (?,?)", (datetime.now(timezone.utc).isoformat(), json.dumps({str(k): str(v) for k, v in trade.items()}, sort_keys=True)))
        self.db.commit()

    def record_equity(self, equity: Decimal, drawdown: Decimal) -> None:
        self.db.execute("INSERT INTO equity(recorded_at,equity,drawdown) VALUES (?,?,?)", (datetime.now(timezone.utc).isoformat(), str(equity), str(drawdown)))
        self.db.commit()

    def trades(self) -> list[dict]:
        return [json.loads(row["payload"]) for row in self.db.execute("SELECT payload FROM trades ORDER BY id")]

    def latest_equity(self) -> dict | None:
        row = self.db.execute("SELECT equity, drawdown, recorded_at FROM equity ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        self.db.close()
