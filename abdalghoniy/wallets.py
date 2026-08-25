import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .wallet_score import WalletMetrics


@dataclass(frozen=True)
class WalletRecord:
    address: str
    venue: str
    observed_at_ms: int
    metrics: WalletMetrics


class PublicWalletCatalog:
    """Load externally collected public-wallet metrics without treating them as trusted instructions."""
    def __init__(self, records: Iterable[WalletRecord] = ()):
        self.records = {r.address.lower(): r for r in records}

    @classmethod
    def from_jsonl(cls, path: Path | str) -> 'PublicWalletCatalog':
        rows=[]
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            item=json.loads(line)
            m=item['metrics']
            metrics=WalletMetrics(item['address'], int(m['age_days']), int(m['closed_trades']), Decimal(str(m['net_pnl'])), Decimal(str(m['profit_factor'])), Decimal(str(m['max_drawdown'])), Decimal(str(m['win_rate'])), Decimal(str(m['top_trade_share'])))
            rows.append(WalletRecord(item['address'], item['venue'], int(item['observed_at_ms']), metrics))
        return cls(rows)

    def eligible(self):
        from .wallet_score import eligible_wallet
        return [r for r in self.records.values() if eligible_wallet(r.metrics)]

    def export(self, path: Path | str) -> None:
        Path(path).write_text('\n'.join(json.dumps({'address': r.address, 'venue': r.venue, 'observed_at_ms': r.observed_at_ms, 'metrics': {k: str(v) for k,v in asdict(r.metrics).items() if k != 'address'}}, sort_keys=True) for r in self.records.values()) + '\n')
