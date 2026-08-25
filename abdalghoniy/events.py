from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from time import time
from typing import Any, Mapping


class EventType(StrEnum):
    MARKET_CANDLE = 'market_candle'
    MARKET_TRADE = 'market_trade'
    ORDER_BOOK = 'order_book'
    FUNDING = 'funding'
    OPEN_INTEREST = 'open_interest'
    WALLET_FILL = 'wallet_fill'
    WALLET_POSITION = 'wallet_position'
    SIGNAL_PROPOSAL = 'signal_proposal'
    RISK_DECISION = 'risk_decision'
    ORDER_INTENT = 'order_intent'
    VENUE_ACK = 'venue_ack'
    FILL = 'fill'
    POSITION = 'position'
    PROTECTION = 'protection'
    LEDGER = 'ledger'


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if hasattr(value, 'as_tuple'):
        return format(value, 'f')
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: EventType
    source: str
    symbol: str
    event_time_ms: int
    ingestion_time_ms: int
    payload: dict[str, Any]
    schema_version: int = 1

    @classmethod
    def create(cls, event_type: EventType, source: str, symbol: str, payload: Mapping[str, Any], *, event_time_ms: int, ingestion_time_ms: int | None = None) -> 'Event':
        if not source or not symbol:
            raise ValueError('source and symbol are required')
        ingestion = ingestion_time_ms if ingestion_time_ms is not None else int(time() * 1000)
        if event_time_ms > ingestion + 300_000:
            raise ValueError('event timestamp is too far in the future')
        normalized = _canonical(dict(payload))
        identity = {'event_type': str(event_type), 'source': source, 'symbol': symbol, 'event_time_ms': event_time_ms, 'payload': normalized, 'schema_version': 1}
        event_id = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return cls(event_id, EventType(event_type), source, symbol, int(event_time_ms), int(ingestion), normalized, 1)

    def to_dict(self) -> dict[str, Any]:
        return {'event_id': self.event_id, 'event_type': self.event_type.value, 'source': self.source, 'symbol': self.symbol, 'event_time_ms': self.event_time_ms, 'ingestion_time_ms': self.ingestion_time_ms, 'payload': self.payload, 'schema_version': self.schema_version}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'Event':
        return cls(str(data['event_id']), EventType(data['event_type']), str(data['source']), str(data['symbol']), int(data['event_time_ms']), int(data['ingestion_time_ms']), dict(data['payload']), int(data.get('schema_version', 1)))
