import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Secrets:
    api_key: str
    api_secret: str


def load_secrets() -> Secrets:
    key = os.environ.get("ABD_EXCHANGE_API_KEY", "")
    secret = os.environ.get("ABD_EXCHANGE_API_SECRET", "")
    return Secrets(key, secret)
