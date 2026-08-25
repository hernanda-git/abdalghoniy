import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromotionEvidence:
    strategy: str
    dataset_hash: str
    code_hash: str
    config_hash: str
    trade_count: int
    net_expectancy: float
    lower_bound: float
    random_control_uplift: float
    oos: bool

    def eligible(self, *, min_trades: int = 100) -> bool:
        return self.oos and self.trade_count >= min_trades and self.net_expectancy > 0 and self.lower_bound > 0 and self.random_control_uplift > 0


class PromotionRegistry:
    def __init__(self, path: Path | str): self.path=Path(path)
    def save(self, evidence: PromotionEvidence) -> None:
        if not evidence.eligible(): raise ValueError('strategy lacks promotion evidence')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps(evidence.__dict__,sort_keys=True,indent=2)+'\n')
    def load(self) -> PromotionEvidence | None:
        if not self.path.exists(): return None
        try: return PromotionEvidence(**json.loads(self.path.read_text()))
        except (OSError,ValueError,TypeError,KeyError): return None
