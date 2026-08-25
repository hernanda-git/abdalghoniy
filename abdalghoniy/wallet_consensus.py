from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class WalletEvent:
    event_id: str
    address: str
    symbol: str
    side: str
    event_time_ms: int
    notional: float
    eligible: bool


@dataclass(frozen=True)
class Consensus:
    symbol: str
    side: str
    addresses: tuple[str, ...]
    first_event_ms: int
    last_event_ms: int


def consensus(events: Iterable[WalletEvent], *, min_wallets: int = 3, window_ms: int = 300_000) -> Consensus | None:
    rows = [e for e in events if e.eligible and e.notional > 0]
    for symbol in sorted({e.symbol for e in rows}):
        for side in ('long', 'short'):
            group = sorted((e for e in rows if e.symbol == symbol and e.side == side), key=lambda e: e.event_time_ms)
            for i, anchor in enumerate(group):
                window = [e for e in group[i:] if e.event_time_ms - anchor.event_time_ms <= window_ms]
                addresses = tuple(sorted({e.address for e in window}))
                if len(addresses) >= min_wallets:
                    return Consensus(symbol, side, addresses, min(e.event_time_ms for e in window), max(e.event_time_ms for e in window))
    return None
