from dataclasses import dataclass
from decimal import Decimal
from math import floor
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
        return len(gates) == 6 and all(g.passed and g.name == expected for g, expected in zip(gates, self.names))


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
