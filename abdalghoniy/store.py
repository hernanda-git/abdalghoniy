from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .events import Event


class EventStore:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            event_time_ms INTEGER NOT NULL,
            ingestion_time_ms INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            symbol TEXT NOT NULL,
            payload TEXT NOT NULL
        )''')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_events_time ON events(event_time_ms, sequence)')
        self.db.commit()

    def append(self, event: Event) -> bool:
        try:
            self.db.execute('INSERT INTO events(event_id,event_time_ms,ingestion_time_ms,event_type,source,symbol,payload) VALUES (?,?,?,?,?,?,?)', (event.event_id, event.event_time_ms, event.ingestion_time_ms, event.event_type.value, event.source, event.symbol, json.dumps(event.to_dict(), sort_keys=True, separators=(',', ':'))))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            self.db.rollback()
            return False

    def append_many(self, events: Iterable[Event]) -> int:
        count = 0
        for event in events:
            count += int(self.append(event))
        return count

    def replay(self, *, symbol: str | None = None) -> list[Event]:
        if symbol:
            rows = self.db.execute('SELECT payload FROM events WHERE symbol=? ORDER BY event_time_ms, sequence', (symbol,)).fetchall()
        else:
            rows = self.db.execute('SELECT payload FROM events ORDER BY event_time_ms, sequence').fetchall()
        return [Event.from_dict(json.loads(row[0])) for row in rows]

    def count(self) -> int:
        return int(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0])

    def close(self) -> None:
        self.db.close()
