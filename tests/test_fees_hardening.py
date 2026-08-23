from decimal import Decimal
import pytest
from abdalghoniy.fees import CostModel, net_pnl


def test_invalid_direction_is_rejected():
    with pytest.raises(ValueError):
        net_pnl(Decimal('100'), Decimal('1'), Decimal('100'), Decimal('101'), 'sideways', CostModel(Decimal('0'),Decimal('0'),Decimal('0')))
