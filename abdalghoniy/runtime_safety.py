from dataclasses import asdict, dataclass
from pathlib import Path
import json, os, tempfile


@dataclass(frozen=True)
class RuntimeSafetyState:
    armed: bool
    halted: bool
    halt_reason: str | None
    data_age_ms: int | None
    last_reconciliation_ms: int | None
    rate_limit_breaker: bool

    @classmethod
    def safe_default(cls):
        return cls(True, False, None, 0, None, False)


class RuntimeSafetyStore:
    def __init__(self, path: Path | str): self.path=Path(path)

    def write(self, state: RuntimeSafetyState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.safety-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w') as f:
                json.dump(asdict(state),f,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def read(self) -> RuntimeSafetyState | None:
        if not self.path.exists(): return None
        try:
            data=json.loads(self.path.read_text())
            return RuntimeSafetyState(bool(data['armed']),bool(data['halted']),data.get('halt_reason'),data.get('data_age_ms'),data.get('last_reconciliation_ms'),bool(data.get('rate_limit_breaker',False)))
        except (OSError,ValueError,KeyError,TypeError):
            return None
