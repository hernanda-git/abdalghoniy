import argparse
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .backtest import counter_trend_diagnostics, replay_counter_trend
from .config import AppConfig
from .data import fetch_demo_candles, fetch_feature_complete_dataset, load_csv
from .dashboard import make_status
from .fees import CostModel
from .ledger import DurableLedger
from .strategies import CounterTrendConfig
from .validation import evaluate_replay
from .shadow import ShadowRunner
from .live_shadow import LiveDemoShadow


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _code_hash() -> str:
    files = [Path(__file__), Path(__file__).with_name("backtest.py"), Path(__file__).with_name("strategies.py"), Path(__file__).with_name("fees.py")]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _replay(args, cfg: AppConfig) -> int:
    input_path = args.input
    if input_path is None:
        input_path = fetch_demo_candles(args.symbol, args.interval, output=Path("data") / f"{args.symbol.lower()}_{args.interval}.csv")
    if not input_path.exists():
        raise SystemExit(f"dataset not found: {input_path}")
    dataset = load_csv(input_path)
    cost = CostModel(
        maker_fee=cfg.round_trip_fee_bps / Decimal("20000"),
        taker_fee=cfg.round_trip_fee_bps / Decimal("20000"),
        slippage_bps=cfg.slippage_bps,
    )
    trades = replay_counter_trend(
        dataset.candles,
        dataset.cvd_changes,
        cost,
        CounterTrendConfig(),
        stop_distance=Decimal(str(args.stop_distance)),
        target_distance=Decimal(str(args.target_distance)),
        max_hold=args.max_hold,
        funding_bps=dataset.funding_bps,
        max_position_notional=cfg.max_position_notional,
    )
    diagnostics = counter_trend_diagnostics(dataset.candles, dataset.cvd_changes, CounterTrendConfig(), dataset.funding_bps)
    gross = sum(((t.entry - t.exit) * t.quantity if t.direction == "short" else (t.exit - t.entry) * t.quantity for t in trades), Decimal("0"))
    net = sum((t.net for t in trades), Decimal("0"))
    funding_total = sum((t.funding for t in trades), Decimal("0"))
    fees_slippage = gross + funding_total - net
    payload = {
        "symbol": args.symbol,
        "interval": args.interval,
        "dataset": str(input_path),
        "dataset_hash": dataset.sha256,
        "code_hash": _code_hash(),
        "config_hash": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "evaluated_at": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
        "candle_count": len(dataset.candles),
        "trade_count": len(trades),
        "gross_pnl": _decimal(gross),
        "fees_slippage": _decimal(fees_slippage),
        "funding": _decimal(funding_total),
        "net_pnl": _decimal(net),
        "expectancy": _decimal(net / Decimal(len(trades))) if trades else None,
        "diagnostics": diagnostics,
        "trades": [
            {"direction": t.direction, "entry": _decimal(t.entry), "exit": _decimal(t.exit), "quantity": _decimal(t.quantity), "net": _decimal(t.net), "funding": _decimal(t.funding), "bars_held": t.bars_held}
            for t in trades
        ],
        "validation": {"status": "research_only", "lookahead_review": "not_passed", "purged_cv": "not_passed", "walk_forward": "not_passed"},
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "ledger.sqlite3"
    ledger = DurableLedger(ledger_path)
    for trade in trades:
        gross_trade = (trade.entry - trade.exit) * trade.quantity if trade.direction == "short" else (trade.exit - trade.entry) * trade.quantity
        ledger.record_trade({"symbol": args.symbol, "direction": trade.direction, "entry": trade.entry, "exit": trade.exit, "quantity": trade.quantity, "gross": gross_trade, "net": trade.net, "funding": trade.funding})
    starting_equity = Decimal("1000")
    ledger.record_equity(starting_equity + net, max(Decimal("0"), -net / starting_equity))
    ledger.close()
    payload["ledger_path"] = str(ledger_path)
    payload["validation"] = evaluate_replay([trade.net for trade in trades], len(dataset.candles))
    (args.output_dir / "latest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


def _shadow(args) -> int:
    dataset = load_csv(args.input)
    runner = ShadowRunner(args.symbol, args.event_path)
    results = []
    for index, candle in enumerate(dataset.candles):
        timestamp = dataset.timestamps[index]
        try:
            from datetime import datetime
            timestamp_value = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            timestamp_value = float(index)
        results.append(runner.process({"timestamp": timestamp_value, "price": str(candle.close), "volume": str(candle.volume)}))
    print(json.dumps({"symbol": args.symbol, "events": len(results), "would_orders": sum(1 for result in results if result["would_order"]), "statuses": {status: sum(1 for result in results if result["status"] == status) for status in sorted({result["status"] for result in results})}, "event_path": str(args.event_path)}, indent=2))
    return 0


def _live_shadow(args) -> int:
    import time
    runner = LiveDemoShadow(args.symbol, args.event_path)
    results = []
    for index in range(args.iterations):
        results.append(runner.poll_once())
        if index + 1 < args.iterations and args.sleep > 0:
            time.sleep(args.sleep)
    print(json.dumps({"symbol": args.symbol, "iterations": len(results), "would_orders": sum(1 for result in results if result.get("would_order")), "statuses": {status: sum(1 for result in results if result.get("status") == status) for status in sorted({result.get("status") for result in results})}, "event_path": str(args.event_path)}, indent=2))
    return 0


def _feature_dataset(args) -> int:
    path = fetch_feature_complete_dataset(args.symbol, args.interval, args.limit, args.output)
    dataset = load_csv(path)
    print(json.dumps({"dataset": str(path), "rows": len(dataset.candles), "cvd_nonzero": sum(1 for value in dataset.cvd_changes if value != 0), "funding_nonzero": sum(1 for value in dataset.funding_bps if value != 0), "dataset_hash": dataset.sha256}, indent=2))
    return 0


def _report(args) -> int:
    path = args.output_dir / "latest.json"
    if not path.exists():
        raise SystemExit(f"no replay report found at {path}")
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ABDALGHONIY paper-only futures research engine")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--status", action="store_true", help="print safety and validation status")
    sub = parser.add_subparsers(dest="command")
    replay = sub.add_parser("replay", help="replay a real CSV dataset in paper mode")
    replay.add_argument("--symbol", required=True)
    replay.add_argument("--interval", required=True)
    replay.add_argument("--input", type=Path, default=None, help="existing CSV; omitted fetches public Bitget SUSDT-FUTURES demo candles")
    replay.add_argument("--output-dir", type=Path, default=Path("reports/latest"))
    replay.add_argument("--stop-distance", default="1")
    replay.add_argument("--target-distance", default="2")
    replay.add_argument("--max-hold", type=int, default=5)
    report = sub.add_parser("report", help="print the latest paper replay report")
    report.add_argument("--latest", action="store_true", required=True)
    report.add_argument("--output-dir", type=Path, default=Path("reports/latest"))
    shadow = sub.add_parser("shadow", help="process market data without any order path")
    shadow.add_argument("--symbol", required=True)
    shadow.add_argument("--input", type=Path, required=True)
    shadow.add_argument("--event-path", type=Path, required=True)
    live_shadow = sub.add_parser("live-shadow", help="poll public Bitget SUSDT-FUTURES candles without orders")
    live_shadow.add_argument("--symbol", required=True)
    live_shadow.add_argument("--event-path", type=Path, required=True)
    live_shadow.add_argument("--iterations", type=int, default=1)
    live_shadow.add_argument("--sleep", type=float, default=1.0)
    feature_dataset = sub.add_parser("feature-dataset", help="build a dataset with public fill CVD and historical funding")
    feature_dataset.add_argument("--symbol", required=True)
    feature_dataset.add_argument("--interval", default="1m")
    feature_dataset.add_argument("--limit", type=int, default=100)
    feature_dataset.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    cfg = AppConfig.from_yaml(args.config)
    if args.command == "replay":
        return _replay(args, cfg)
    if args.command == "report":
        return _report(args)
    if args.command == "shadow":
        return _shadow(args)
    if args.command == "live-shadow":
        return _live_shadow(args)
    if args.command == "feature-dataset":
        return _feature_dataset(args)
    if args.status:
        print(json.dumps({"config": {"mode": cfg.mode, "max_leverage": str(cfg.max_leverage), "max_drawdown": str(cfg.max_drawdown), "max_position_notional": str(cfg.max_position_notional)}, "status": make_status(Path.cwd())}, indent=2))
    else:
        print("ABDALGHONIY loaded in paper mode. No live orders are available in this build.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
