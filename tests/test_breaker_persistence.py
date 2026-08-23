from decimal import Decimal
from pathlib import Path
from datetime import date
import json

from abdalghoniy.risk import DailyLossBreaker


def test_daily_breaker_persists_and_resets_by_day(tmp_path):
    state=tmp_path/'breaker.json'
    b=DailyLossBreaker(Decimal('1000'),Decimal('50'),state_path=state)
    b.record_equity(Decimal('950'),day='2026-08-23')
    assert DailyLossBreaker(Decimal('1000'),Decimal('50'),state_path=state).tripped
    b.record_equity(Decimal('1000'),day='2026-08-24')
    assert not b.tripped
