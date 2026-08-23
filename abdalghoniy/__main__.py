import argparse
import json
from pathlib import Path

from .config import AppConfig
from .dashboard import make_status


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='ABDALGHONIY paper-only futures research engine')
    parser.add_argument('--config', type=Path, default=Path('config.yaml'))
    parser.add_argument('--status', action='store_true', help='print safety and validation status')
    args = parser.parse_args(argv)
    cfg = AppConfig.from_yaml(args.config)
    if args.status:
        print(json.dumps({'config': {'mode': cfg.mode, 'max_leverage': str(cfg.max_leverage), 'max_drawdown': str(cfg.max_drawdown), 'max_position_notional': str(cfg.max_position_notional)}, 'status': make_status(Path.cwd())}, indent=2))
    else:
        print('ABDALGHONIY loaded in paper mode. No live orders are available in this build.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
