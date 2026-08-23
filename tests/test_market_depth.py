import pytest

from abdalghoniy.market_depth import OrderBookAggregator, PublicOrderBookClient, ProductTypeError


def test_aggregates_bid_ask_spread_depth_and_imbalance():
    book = OrderBookAggregator.from_bitget({
        "bids": [["100", "2"], ["99", "3"]],
        "asks": [["101", "1"], ["102", "4"]],
        "ts": "1700000000123",
    }, depth_levels=2)

    assert book.best_bid == 100.0
    assert book.best_ask == 101.0
    assert book.spread == 1.0
    assert book.bid_depth == 5.0
    assert book.ask_depth == 5.0
    assert book.imbalance == 0.0
    assert book.timestamp_ms == 1700000000123
    assert book.status == "ok"


def test_empty_or_crossed_book_is_unavailable_not_estimated():
    empty = OrderBookAggregator.from_bitget({"bids": [], "asks": []})
    assert empty.status == "unavailable"
    assert empty.best_bid is None
    assert empty.imbalance is None

    crossed = OrderBookAggregator.from_bitget({"bids": [["101", "1"]], "asks": [["100", "1"]]})
    assert crossed.status == "unavailable"
    assert crossed.error == "crossed_order_book"


def test_public_client_uses_only_demo_product_and_public_depth_endpoint():
    calls = []

    def transport(method, url, headers=None, body=None):
        calls.append((method, url, headers, body))
        return {"code": "00000", "data": {"bids": [["100", "2"]], "asks": [["101", "3"]], "ts": "1"}}

    client = PublicOrderBookClient(transport=transport)
    result = client.fetch("BTCUSDT", limit=20)

    assert result.status == "ok"
    assert calls[0][0] == "GET"
    assert "/api/v2/mix/market/merge-depth" in calls[0][1]
    assert "productType=SUSDT-FUTURES" in calls[0][1]
    assert "symbol=SBTCSUSDT" in calls[0][1]
    assert "limit=20" in calls[0][1]
    assert calls[0][2] == {}
    assert "USDT-FUTURES" not in calls[0][1].replace("SUSDT-FUTURES", "")


def test_public_client_reports_transport_failure_and_never_calls_order_path():
    def transport(*args, **kwargs):
        raise TimeoutError("timeout")

    result = PublicOrderBookClient(transport=transport).fetch("BTCUSDT")
    assert result.status == "unavailable"
    assert result.error == "timeout"


def test_client_rejects_live_product_type():
    with pytest.raises(ProductTypeError):
        PublicOrderBookClient(product_type="USDT-FUTURES")
