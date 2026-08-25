from dataclasses import dataclass


@dataclass(frozen=True)
class CopyabilityObservation:
    wallet_event_ms: int
    observed_ms: int
    decision_ms: int
    wallet_price: float
    observed_price: float
    decision_price: float
    atr: float
    move_atr: float


def copyable(obs: CopyabilityObservation, *, max_delay_ms: int = 500, max_atr_move: float = 0.4) -> bool:
    if obs.observed_ms < obs.wallet_event_ms or obs.decision_ms < obs.observed_ms:
        return False
    if obs.decision_ms - obs.wallet_event_ms > max_delay_ms or obs.atr <= 0:
        return False
    move = abs(obs.decision_price - obs.wallet_price) / obs.atr
    return move <= max_atr_move
