from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo
import json


class StopSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class HardStop:
    side: StopSide
    price: Decimal

    def __post_init__(self):
        if self.price <= 0:
            raise ValueError("stop price must be positive")

    @classmethod
    def for_entry(cls, direction: str, entry: Decimal, distance: Decimal) -> "HardStop":
        if entry <= 0 or distance <= 0:
            raise ValueError("entry and stop distance must be positive")
        if direction.lower() == "long":
            return cls(StopSide.SELL, entry - distance)
        if direction.lower() == "short":
            return cls(StopSide.BUY, entry + distance)
        raise ValueError("direction must be long or short")


class DailyLossBreaker:
    def __init__(self, starting_equity: Decimal, max_loss: Decimal, state_path: Optional[Path] = None):
        if starting_equity <= 0 or max_loss <= 0:
            raise ValueError("equity and loss cap must be positive")
        self.starting_equity = starting_equity
        self.max_loss = max_loss
        self.state_path = Path(state_path) if state_path else None
        self.day = None
        self.tripped = False
        self._load()

    def _today(self) -> str:
        return datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat()

    def _load(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text())
            if data.get('day') == self._today():
                self.day = data['day']
                self.tripped = bool(data.get('tripped', False))
        except (OSError, ValueError, TypeError):
            self.tripped = True

    def _save(self) -> None:
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps({'day': self.day, 'tripped': self.tripped}))

    def record_equity(self, equity: Decimal, day: Optional[str] = None) -> None:
        current_day = day or self._today()
        if self.day != current_day:
            self.day = current_day
            self.tripped = False
        if equity <= self.starting_equity - self.max_loss:
            self.tripped = True
        self._save()

    def allow_new_risk(self) -> None:
        if self.tripped:
            raise PermissionError("daily loss breaker is tripped")
