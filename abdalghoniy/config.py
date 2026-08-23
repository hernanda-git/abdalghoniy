from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

import yaml


@dataclass(frozen=True)
class AppConfig:
    mode: str = "paper"
    max_leverage: Decimal = Decimal("3")
    max_drawdown: Decimal = Decimal("0.02")
    round_trip_fee_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("2")
    max_position_notional: Decimal = Decimal("1000")

    @classmethod
    def from_yaml(cls, path: Path):
        data = yaml.safe_load(Path(path).read_text()) or {}
        if not isinstance(data, dict):
            raise ValueError("config root must be a mapping")
        return cls.from_mapping(data)

    @classmethod
    def from_mapping(cls, data: Mapping):
        allowed = {"mode", "max_leverage", "max_drawdown", "round_trip_fee_bps", "slippage_bps", "max_position_notional"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        mode = str(data.get("mode", "paper"))
        if mode != "paper":
            raise ValueError("only paper mode is enabled in this build")
        try:
            values = {k: Decimal(str(data.get(k, default))) for k, default in {
                "max_leverage": "3", "max_drawdown": "0.02", "round_trip_fee_bps": "10", "slippage_bps": "2", "max_position_notional": "1000"}.items()}
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("numeric config value is invalid") from exc
        if any(v.is_nan() or v.is_infinite() for v in values.values()):
            raise ValueError("numeric config value must be finite")
        if not (Decimal("0") < values["max_leverage"] <= Decimal("3")):
            raise ValueError("max_leverage must be in (0, 3]")
        if not (Decimal("0") < values["max_drawdown"] < Decimal("1")):
            raise ValueError("max_drawdown must be in (0, 1)")
        if values["round_trip_fee_bps"] < 0 or values["slippage_bps"] < 0 or values["max_position_notional"] <= 0:
            raise ValueError("fees/slippage must be non-negative and notional must be positive")
        return cls(mode, **values)
