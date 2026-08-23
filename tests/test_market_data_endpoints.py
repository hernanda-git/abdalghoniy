from abdalghoniy.market_data import PublicBitgetMarketData


def test_candles_and_depth_use_documented_public_paths():
    calls = []

    def transport(method, url, headers=None, body=None):
        calls.append(url)
        if "candles" in url:
            return {"code": "00000", "data": [["1700000000000", "1", "2", "0.5", "1.5", "10"]]}
        return {"code": "00000", "data": {"bids": [["1", "2"]], "asks": [["2", "3"]], "ts": "1700000000000"}}

    client = PublicBitgetMarketData(transport=transport, clock_ms=lambda: 1700000001000)
    candles = client.candles("BTCUSDT", granularity="1m", limit=10)
    depth = client.depth("BTCUSDT", limit=20)

    assert candles.data[0][4] == "1.5"
    assert candles.metadata.method == "GET /api/v2/mix/market/candles"
    assert candles.metadata.freshness_ms == 1000
    assert depth.data["bids"] == [["1", "2"]]
    assert depth.metadata.method == "GET /api/v2/mix/market/orderbook"
    assert all("productType=SUSDT-FUTURES" in url and "symbol=SBTCSUSDT" in url for url in calls)
    assert all("/order/" not in url for url in calls)
