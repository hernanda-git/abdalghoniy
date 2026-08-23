from decimal import Decimal

import pytest

from abdalghoniy.config import AppConfig


def test_yaml_config_loads_all_safety_fields(tmp_path):
    p = tmp_path / 'config.yaml'
    p.write_text('mode: paper\nmax_leverage: 2\nmax_drawdown: 0.03\nround_trip_fee_bps: 10\nslippage_bps: 2\nmax_position_notional: 500\n')
    cfg = AppConfig.from_yaml(p)
    assert cfg.max_position_notional == Decimal('500')
    assert cfg.round_trip_fee_bps == Decimal('10')
    assert cfg.slippage_bps == Decimal('2')


def test_config_rejects_unknown_keys_and_nonpaper_modes(tmp_path):
    p = tmp_path / 'bad.yaml'
    p.write_text('mode: shadow\nunknown: 1\n')
    with pytest.raises(ValueError):
        AppConfig.from_yaml(p)
