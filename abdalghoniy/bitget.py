import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable


class ProductTypeError(ValueError):
    pass


@dataclass(frozen=True)
class ContractSpec:
    symbol: str
    min_trade_num: float
    size_multiplier: float
    volume_place: int
    price_place: int
    min_trade_usdt: float


class BitgetReadOnlyClient:
    """Bitget V2 read-only client restricted to the SUSDT demo product."""

    def __init__(self, api_key: str = "", api_secret: str = "", passphrase: str = "", *, product_type: str = "SUSDT-FUTURES", base_url: str = "https://api.bitget.com", transport: Callable | None = None, clock_ms: Callable[[], int] | None = None):
        if product_type != "SUSDT-FUTURES":
            raise ProductTypeError("ABDALGHONIY permits only SUSDT-FUTURES")
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.product_type = product_type
        self.base_url = base_url.rstrip("/")
        self.transport = transport or self._urlopen_transport
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))

    @staticmethod
    def venue_symbol(symbol: str) -> str:
        symbol = symbol.upper()
        if symbol.startswith("S") and symbol.endswith("SUSDT"):
            return symbol
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        return f"S{base}SUSDT"

    @staticmethod
    def _urlopen_transport(method: str, url: str, headers=None, body=None):
        request = urllib.request.Request(url, method=method, headers=headers or {}, data=body.encode() if body else None)
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def _headers(self, method: str, request_path: str) -> dict[str, str]:
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {}
        timestamp = str(self.clock_ms())
        prehash = timestamp + method.upper() + request_path
        signature = base64.b64encode(hmac.new(self.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()
        return {"ACCESS-KEY": self.api_key, "ACCESS-SIGN": signature, "ACCESS-TIMESTAMP": timestamp, "ACCESS-PASSPHRASE": self.passphrase, "Content-Type": "application/json", "locale": "en-US"}

    def _get(self, path: str, params: dict[str, str], signed: bool = False):
        query = urllib.parse.urlencode(params)
        request_path = f"{path}?{query}"
        payload = self.transport("GET", self.base_url + request_path, headers=self._headers("GET", request_path) if signed else {}, body=None)
        if payload.get("code") != "00000":
            raise RuntimeError(f"Bitget read-only request failed: {payload.get('code')}")
        return payload.get("data") or []

    def contract(self, symbol: str) -> dict:
        rows = self._get("/api/v2/mix/market/contracts", {"productType": self.product_type, "symbol": self.venue_symbol(symbol)})
        if not rows:
            raise RuntimeError(f"no demo contract for {symbol}")
        return rows[0]

    def ticker(self, symbol: str) -> dict:
        rows = self._get("/api/v2/mix/market/ticker", {"productType": self.product_type, "symbol": self.venue_symbol(symbol)})
        if not rows:
            raise RuntimeError(f"no demo ticker for {symbol}")
        return rows[0]

    def demo_account(self) -> list[dict]:
        return self._get("/api/v2/mix/account/accounts", {"productType": self.product_type}, signed=True)

    def demo_positions(self) -> list[dict]:
        return self._get("/api/v2/mix/position/all-position", {"productType": self.product_type}, signed=True)
