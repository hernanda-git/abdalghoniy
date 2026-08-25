from decimal import Decimal
from abdalghoniy.config import AppConfig


def test_default_config_is_sized_for_ten_dollar_account():
    cfg=AppConfig.from_yaml('/root/abdalghoniy/config.yaml')
    assert cfg.max_position_notional <= Decimal('10')
    assert cfg.max_leverage <= Decimal('3')
    assert cfg.max_drawdown <= Decimal('0.03')
