import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Secrets:
    api_key: str
    api_secret: str
    passphrase: str


def load_secrets() -> Secrets:
    # User-mandated naming (BITGET_*) with legacy ABD_EXCHANGE_ fallback.
    key = os.environ.get("BITGET_API_KEY") or os.environ.get("ABD_EXCHANGE_API_KEY", "")
    secret = os.environ.get("BITGET_API_SECRET") or os.environ.get("ABD_EXCHANGE_API_SECRET", "")
    passphrase = os.environ.get("BITGET_PASSPHRASE") or os.environ.get("ABD_EXCHANGE_PASSPHRASE", "")
    return Secrets(key, secret, passphrase)


def has_secrets() -> bool:
    s = load_secrets()
    return bool(s.api_key and s.api_secret and s.passphrase)
