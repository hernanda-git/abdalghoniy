import json
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from abdalghoniy.events import Event, EventType
from abdalghoniy.store import EventStore


def test_event_has_deterministic_id_and_decimal_safe_payload():
    event = Event.create(EventType.MARKET_CANDLE, 'bitget', 'SBTCSUSDT', {'close': Decimal('100.1')}, event_time_ms=1000)
    assert event.event_id == Event.create(EventType.MARKET_CANDLE, 'bitget', 'SBTCSUSDT', {'close': Decimal('100.1')}, event_time_ms=1000).event_id
    payload = event.to_dict()
    assert payload['payload']['close'] == '100.1'
    assert payload['schema_version'] == 1


def test_event_store_is_idempotent_and_replays_in_order(tmp_path):
    store = EventStore(tmp_path / 'events.sqlite3')
    event = Event.create(EventType.MARKET_TRADE, 'bitget', 'SBTCSUSDT', {'price': '100', 'qty': '1'}, event_time_ms=1000)
    assert store.append(event) is True
    assert store.append(event) is False
    rows = store.replay()
    assert len(rows) == 1
    assert rows[0].event_id == event.event_id
    store.close()


def test_event_rejects_future_ingestion_and_invalid_identity():
    with pytest.raises(ValueError):
        Event.create(EventType.MARKET_TRADE, '', 'SBTCSUSDT', {}, event_time_ms=1000)
    with pytest.raises(ValueError):
        Event.create(EventType.MARKET_TRADE, 'bitget', 'SBTCSUSDT', {}, event_time_ms=10**16, ingestion_time_ms=1000)
