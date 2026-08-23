from decimal import Decimal
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo
import json

from abdalghoniy.risk import DailyLossBreaker


def test_daily_breaker_persists_and_resets_by_day(tmp_path):
    state=tmp_path/'breaker.json'
    today = datetime.now(ZoneInfo('Asia/Jakarta')).date()
    b=DailyLossBreaker(Decimal('1000'),Decimal('50'),state_path=state)
    b.record_equity(Decimal('950'),day=today.isoformat())
    assert DailyLossBreaker(Decimal('1000'),Decimal('50'),state_path=state).tripped
    b.record_equity(Decimal('1000'),day=(today + date.resolution).isoformat())
    assert not b.tripped
