"""Explicitly unavailable liquidation heatmap for the SUSDT demo venue.

No reliable public SUSDT-FUTURES liquidation stream is exposed by the supported
read-only surface. This module deliberately returns unavailable instead of
estimating liquidation levels from trades, candles, open interest, or prices.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class LiquidationHeatmap:
    status: str
    source: str
    levels: tuple = ()
    total_notional: float | None = None
    freshness_ms: int | None = None
    error: str | None = None


class PublicLiquidationHeatmapClient:
    """Fail-closed liquidation handler with no unsupported network endpoint."""

    UNAVAILABLE_REASON = "no_reliable_public_susdt_futures_liquidation_stream"

    def __init__(self, *, transport: Callable | None = None):
        self.transport = transport

    def fetch(self, symbol: str) -> LiquidationHeatmap:
        del symbol
        return LiquidationHeatmap(
            status="unavailable",
            source="none",
            error=self.UNAVAILABLE_REASON,
        )
