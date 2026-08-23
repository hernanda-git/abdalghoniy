from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True)
class AppConfig:
    mode: str = "paper"
    max_leverage: Decimal = Decimal("3")
    max_drawdown: Decimal = Decimal("0.02")

    @classmethod
    def from_mapping(cls, data: Mapping):
        mode = str(data.get("mode", "paper"))
        if mode not in {"paper", "shadow", "micro_live"}:
            raise ValueError("mode must be paper, shadow, or micro_live")
        lev = Decimal(str(data.get("max_leverage", "3")))
        dd = Decimal(str(data.get("max_drawdown", "0.02")))
        if lev <= 0 or lev > 3 or dd <= 0:
            raise ValueError("unsafe config limits")
        return cls(mode, lev, dd)
