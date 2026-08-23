from abdalghoniy.market_data import PublicBitgetMarketData


def test_empty_public_payload_is_unavailable():
    client = PublicBitgetMarketData(transport=lambda *args, **kwargs: {"code": "00000", "data": []})
    result = client.ticker("BTCUSDT")
    assert result.data is None
    assert result.metadata.unavailable is True
    assert result.metadata.error == "RuntimeError"
