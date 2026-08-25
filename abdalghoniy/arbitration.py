from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class Proposal:
    side: str
    expected_edge_bps: Decimal
    confidence: Decimal
    source: str
    regime_agrees: bool
    derivatives_agree: bool
    microstructure_ok: bool
    expires_at_ms: int


def arbitrate(proposals: Iterable[Proposal], *, min_edge_bps: Decimal, now_ms: int | None = None) -> Proposal | None:
    candidates=[]
    for p in proposals:
        if p.side not in {'long','short'} or p.expected_edge_bps < min_edge_bps or not (Decimal('0') <= p.confidence <= Decimal('1')):
            continue
        if not (p.regime_agrees and p.derivatives_agree and p.microstructure_ok):
            continue
        if now_ms is not None and now_ms > p.expires_at_ms:
            continue
        candidates.append(p)
    return max(candidates, key=lambda p: (p.expected_edge_bps, p.confidence), default=None)
