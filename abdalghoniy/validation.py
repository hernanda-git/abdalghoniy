import json
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Tuple


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str


class ValidationLadder:
    names = ("logic_review", "purged_cv", "deflated_metric", "walk_forward", "shadow", "micro_live")

    def can_trade(self, cost_edge_bps: Decimal, round_trip_fee_bps: Decimal, expectancy: Decimal) -> bool:
        return cost_edge_bps >= round_trip_fee_bps * Decimal("2") and expectancy > 0

    def authorize(self, gates: List[GateResult]) -> bool:
        if len(gates) != 6 or not all(g.passed and g.name == expected for g, expected in zip(gates, self.names)):
            return False
        required = {"dataset_hash", "evaluated_at", "code_hash", "metric"}
        for gate in gates:
            try:
                evidence = json.loads(gate.detail)
            except (TypeError, json.JSONDecodeError):
                return False
            if not required.issubset(evidence) or not all(evidence[k] not in ("", None) for k in required):
                return False
        return True


def purged_splits(n_samples: int, folds: int = 5, purge: int = 1, embargo: int = 1) -> List[Tuple[list, list]]:
    if n_samples <= 0 or folds < 2 or purge < 0 or embargo < 0:
        raise ValueError("invalid split parameters")
    block = n_samples // folds
    result = []
    for i in range(folds):
        start, end = i * block, n_samples if i == folds - 1 else (i + 1) * block
        test = list(range(start, end))
        train = list(range(0, max(0, start - purge))) + list(range(min(n_samples, end + embargo), n_samples))
        result.append((train, test))
    return result


def wilson_lower_bound(wins: int, trials: int, z: Decimal = Decimal("1.96")) -> Decimal:
    if trials <= 0 or wins < 0 or wins > trials:
        raise ValueError("invalid binomial counts")
    p = Decimal(wins) / Decimal(trials)
    zz = z * z
    denom = Decimal(1) + zz / Decimal(trials)
    centre = p + zz / (Decimal(2) * Decimal(trials))
    spread = z * ((p * (Decimal(1) - p) / Decimal(trials) + zz / (Decimal(4) * Decimal(trials) ** 2)).sqrt())
    return (centre - spread) / denom


def evaluate_replay(returns, sample_count: int) -> dict:
    """Produce conservative, executable validation evidence from realized returns."""
    values = [Decimal(str(value)) for value in returns]
    trade_count = len(values)
    wins = sum(1 for value in values if value > 0)
    lower = wilson_lower_bound(wins, trade_count) if trade_count else Decimal("0")
    splits = purged_splits(sample_count) if sample_count >= 5 else []
    enough = trade_count >= 30
    return {
        "status": "research_only" if enough else "insufficient_evidence",
        "trade_count": trade_count,
        "mean_return": str(sum(values, Decimal("0")) / Decimal(trade_count)) if values else None,
        "purged_cv": {"status": "not_passed" if not enough else "implemented_not_passed", "folds": len(splits), "purge": 1, "embargo": 1},
        "deflated_metric": {"status": "not_passed", "reason": "requires multiple tested configurations and sufficient trades"},
        "walk_forward": {"status": "not_passed" if not enough else "implemented_not_passed", "test_fraction": "0.30"},
        "confidence_interval": {"wins": wins, "trials": trade_count, "wilson_lower_win_rate": str(lower), "positive_lower_bound": bool(enough and lower > Decimal("0.5"))},
        "random_control": {"status": "not_passed" if not enough else "implemented_not_passed", "reason": "matched random-entry replay is required before promotion"},
        "multi_symbol_window": {"status": "not_passed", "reason": "requires independent symbol and window datasets"},
    }
