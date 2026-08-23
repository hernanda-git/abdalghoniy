import base64
import hashlib
import hmac
import json

import pytest

from abdalghoniy.bitget import BitgetReadOnlyClient, ProductTypeError


def test_read_only_client_rejects_live_product():
    with pytest.raises(ProductTypeError):
        BitgetReadOnlyClient(product_type="USDT-FUTURES")


def test_demo_contract_and_ticker_use_demo_symbol_and_public_paths():
    calls = []

    def transport(method, url, headers=None, body=None):
        calls.append((method, url, headers, body))
        if "contracts" in url:
            return {"code": "00000", "data": [{"symbol": "SBTCSUSDT", "minTradeNum": "1", "sizeMultiplier": "1", "volumePlace": "0", "pricePlace": "1", "minTradeUSDT": "5"}]}
        return {"code": "00000", "data": [{"symbol": "SBTCSUSDT", "lastPr": "100"}]}

    client = BitgetReadOnlyClient(transport=transport)
    spec = client.contract("BTCUSDT")
    ticker = client.ticker("BTCUSDT")
    assert spec["symbol"] == "SBTCSUSDT"
    assert ticker["lastPr"] == "100"
    assert "productType=SUSDT-FUTURES" in calls[0][1]
    assert "symbol=SBTCSUSDT" in calls[0][1]
    assert all("order" not in call[1] for call in calls)


def test_signed_account_read_has_bitget_signature_without_order_surface():
    seen = {}

    def transport(method, url, headers=None, body=None):
        seen.update(method=method, url=url, headers=headers or {}, body=body)
        return {"code": "00000", "data": [{"available": "3000"}]}

    client = BitgetReadOnlyClient(api_key="k", api_secret="s", passphrase="p", transport=transport, clock_ms=lambda: 1700000000000)
    result = client.demo_account()
    assert result[0]["available"] == "3000"
    assert seen["url"].endswith("productType=SUSDT-FUTURES")
    expected = base64.b64encode(hmac.new(b"s", b"1700000000000GET/api/v2/mix/account/accounts?productType=SUSDT-FUTURES", hashlib.sha256).digest()).decode()
    assert seen["headers"]["ACCESS-SIGN"] == expected
