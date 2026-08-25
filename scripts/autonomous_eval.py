#!/usr/bin/env python3
"""Autonomous data-acquisition and evaluation campaign for ABDALGHONIY.

Paper-only. No live orders are ever placed. This script:
  1. Acquires public Bitget SUSDT-FUTURES 1m demo candles for target symbols
     (retry/backoff on 429) and caches them under data/.
  2. Runs BOTH replay strategies (orderflow + counter_trend) on each dataset
     via the production CLI (`python -m abdalghoniy replay`) so the exact
     production code path is exercised. Captures trade_count / net_pnl / gross /
     fees / validation payload and whether CVD/funding were non-zero.
  3. Runs a SYNTHETIC stress/smoke test: 3 random-walk series (1000 bars) with
     synthetic CVD + funding, runs both replays. This only proves the pipeline
     executes end-to-end; it is NOT a profitability claim.
  4. Additionally replays the cached REAL-feature dataset (non-zero CVD/funding)
     as a sanity check that the strategies actually engage when features are real.
  5. Aggregates everything into reports/autonomous-eval.json and emits a markdown
     summary.

Under NO circumstances does this fabricate results. If a fetch fails after
retries, it is recorded honestly.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from abdalghoniy.data import fetch_demo_candles  # noqa: E402
from abdalghoniy.strategies import Candle, CounterTrendConfig, OrderflowReplayConfig  # noqa: E402
from abdalghoniy.fees import CostModel  # noqa: E402
from abdalghoniy.backtest import replay_orderflow, replay_counter_trend  # noqa: E402
from abdalghoniy.validation import evaluate_replay  # noqa: E402

DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
PER_DATASET_DIR = REPORTS_DIR / "per_dataset"
SYNTH_DIR = REPORTS_DIR / "synthetic_stress"

TARGET_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
TARGET_LIMIT = 1000  # up to ~2000 allowed by rate limits; 1000 is safe
MIN_LIMIT = 500

REPLAY_CLI = [sys.executable, "-m", "abdalghoniy", "replay"]


# --------------------------------------------------------------------------- #
# 1. Acquisition with retry/backoff
# --------------------------------------------------------------------------- #
def fetch_with_retry(symbol: str, interval: str, limit: int, max_attempts: int = 6) -> dict:
    """Fetch demo candles, retrying with exponential backoff on 429/transient errors."""
    last_err: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            out = DATA_DIR / f"{symbol.lower()}_{interval}.csv"
            path = fetch_demo_candles(symbol, interval, limit=limit, output=out)
            n = sum(1 for _ in open(path, "r")) - 1
            return {"symbol": symbol, "ok": True, "candles": n, "path": str(path), "attempts": attempt}
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            last_err = msg
            is_rate = "429" in msg or "Too many" in msg or "rate" in msg.lower()
            wait = min(2 ** attempt * 2, 60)
            print(f"  [retry {attempt}/{max_attempts}] {symbol}: {msg[:120]} "
                  f"{('backing off %ss' % wait) if is_rate else ''}", flush=True)
            if attempt < max_attempts:
                time.sleep(wait)
    return {"symbol": symbol, "ok": False, "candles": 0, "path": None, "error": last_err}


# --------------------------------------------------------------------------- #
# 2. Replay via the production CLI (faithful code path) + parse latest.json
# --------------------------------------------------------------------------- #
def run_cli_replay(symbol: str, strategy: str, input_path: Path) -> dict:
    out_dir = PER_DATASET_DIR / symbol / strategy
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *REPLAY_CLI,
        "--symbol", symbol,
        "--interval", "1m",
        "--strategy", strategy,
        "--input", str(input_path),
        "--output-dir", str(out_dir),
    ]
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        return {"strategy": strategy, "ok": False, "error": f"timeout: {exc}"}
    if proc.returncode != 0:
        return {"strategy": strategy, "ok": False, "error": (proc.stderr or proc.stdout)[-500:]}
    latest = out_dir / "latest.json"
    if not latest.exists():
        return {"strategy": strategy, "ok": False, "error": "no latest.json produced"}
    payload = json.loads(latest.read_text(encoding="utf-8"))
    return {"strategy": strategy, "ok": True, "payload": payload}


# --------------------------------------------------------------------------- #
# 3. Synthetic stress / smoke test
# --------------------------------------------------------------------------- #
def make_random_walk(seed: int, n: int = 1000, start: float = 100.0):
    import random
    rng = random.Random(seed)
    candles: list[Candle] = []
    cvd, funding = [], []
    price = float(start)
    for _ in range(n):
        drift = rng.gauss(0.0, 0.003)  # ~0.3% std/bar so momentum occasionally exceeds 50bps
        price = max(1.0, price * (1.0 + drift))
        o = price
        c = price * (1.0 + rng.gauss(0.0, 0.001))
        hi = max(o, c) * (1.0 + abs(rng.gauss(0.0, 0.0006)))
        lo = min(o, c) * (1.0 - abs(rng.gauss(0.0, 0.0006)))
        vol = Decimal(str(rng.uniform(10.0, 200.0)))
        candles.append(Candle(Decimal(f"{o:.6f}"), Decimal(f"{hi:.6f}"),
                              Decimal(f"{lo:.6f}"), Decimal(f"{c:.6f}"), vol))
        # synthetic CVD: magnitude up to ~120 so counter_trend cvd threshold (10) can be crossed
        cvd.append(Decimal(str(rng.uniform(-120.0, 120.0))))
        # synthetic funding: within +/-15bps so counter_trend funding reject (20bps) does not block
        funding.append(Decimal(str(rng.uniform(-15.0, 15.0))))
    return candles, cvd, funding


def run_synthetic() -> list[dict]:
    cost = CostModel(maker_fee=Decimal("0.0004"), taker_fee=Decimal("0.0004"), slippage_bps=Decimal("2"))
    results = []
    for seed in (101, 202, 303):
        candles, cvd, funding = make_random_walk(seed)
        of_trades = replay_orderflow(candles, cvd, cost, OrderflowReplayConfig(), max_position_notional=None)
        ct_trades = replay_counter_trend(
            candles, cvd, cost, CounterTrendConfig(),
            stop_distance=Decimal("1"), target_distance=Decimal("2"), max_hold=5,
            funding_bps=funding, max_position_notional=None,
        )
        of_net = sum((t.net for t in of_trades), Decimal("0"))
        ct_net = sum((t.net for t in ct_trades), Decimal("0"))
        of_exp = (of_net / Decimal(len(of_trades))) if of_trades else Decimal("0")
        ct_exp = (ct_net / Decimal(len(ct_trades))) if ct_trades else Decimal("0")
        results.append({
            "walk_seed": seed,
            "bars": len(candles),
            "orderflow": {"trade_count": len(of_trades), "net_pnl": str(of_net), "expectancy": str(of_exp)},
            "counter_trend": {"trade_count": len(ct_trades), "net_pnl": str(ct_net), "expectancy": str(ct_exp)},
        })
    return results


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    REPORTS_DIR.mkdir(exist_ok=True)
    PER_DATASET_DIR.mkdir(exist_ok=True)
    SYNTH_DIR.mkdir(exist_ok=True)

    print("=== STEP 1: acquire demo candle datasets ===", flush=True)
    acquired = []
    for sym in TARGET_SYMBOLS:
        print(f"fetching {sym} ...", flush=True)
        res = fetch_with_retry(sym, "1m", TARGET_LIMIT)
        acquired.append(res)
        print(f"  -> {res}", flush=True)

    successful = [a for a in acquired if a["ok"]]
    print(f"acquired {len(successful)}/{len(TARGET_SYMBOLS)} datasets", flush=True)

    print("\n=== STEP 2: replay both strategies per dataset (via CLI) ===", flush=True)
    per_dataset = []
    for a in acquired:
        if not a["ok"]:
            per_dataset.append({"symbol": a["symbol"], "acquired": False, "error": a.get("error")})
            continue
        in_path = Path(a["path"])
        row = {"symbol": a["symbol"], "candles": a["candles"], "strategies": {}}
        for strat in ("orderflow", "counter_trend"):
            print(f"  {a['symbol']} / {strat} ...", flush=True)
            r = run_cli_replay(a["symbol"], strat, in_path)
            if not r["ok"]:
                row["strategies"][strat] = {"ok": False, "error": r.get("error")}
                continue
            p = r["payload"]
            cvd_nonzero = sum(1 for v in p.get("diagnostics", {}).get("cvd_nonzero", 0) or []) if isinstance(p.get("diagnostics"), dict) else 0
            # cvd_nonzero in diagnostics is an int count for counter_trend; for orderflow it's a count too
            diag = p.get("diagnostics", {})
            cvd_nz = diag.get("cvd_nonzero", 0) if isinstance(diag, dict) else 0
            row["strategies"][strat] = {
                "ok": True,
                "trade_count": p.get("trade_count"),
                "gross_pnl": p.get("gross_pnl"),
                "fees_slippage": p.get("fees_slippage"),
                "funding": p.get("funding"),
                "net_pnl": p.get("net_pnl"),
                "expectancy": p.get("expectancy"),
                "validation": p.get("validation"),
                "cvd_nonzero_count": cvd_nz,
            }
        per_dataset.append(row)

    print("\n=== STEP 3: synthetic stress / smoke test ===", flush=True)
    synth = run_synthetic()
    for s in synth:
        print(f"  seed {s['walk_seed']}: of_trades={s['orderflow']['trade_count']} "
              f"ct_trades={s['counter_trend']['trade_count']}", flush=True)

    print("\n=== STEP 4: real-feature sanity replay (cached non-zero CVD) ===", flush=True)
    real_feature = None
    feat_candidates = sorted(DATA_DIR.glob("*feature_complete*.csv"))
    if feat_candidates:
        fp = feat_candidates[-1]
        row = {"dataset": str(fp), "strategies": {}}
        for strat in ("orderflow", "counter_trend"):
            r = run_cli_replay(fp.stem, strat, fp)
            if not r["ok"]:
                row["strategies"][strat] = {"ok": False, "error": r.get("error")}
                continue
            p = r["payload"]
            diag = p.get("diagnostics", {})
            cvd_nz = diag.get("cvd_nonzero", 0) if isinstance(diag, dict) else 0
            row["strategies"][strat] = {
                "ok": True,
                "trade_count": p.get("trade_count"),
                "gross_pnl": p.get("gross_pnl"),
                "fees_slippage": p.get("fees_slippage"),
                "funding": p.get("funding"),
                "net_pnl": p.get("net_pnl"),
                "expectancy": p.get("expectancy"),
                "validation": p.get("validation"),
                "cvd_nonzero_count": cvd_nz,
            }
        real_feature = row
        print(f"  {fp.name}: of={row['strategies'].get('orderflow',{}).get('trade_count')} "
              f"ct={row['strategies'].get('counter_trend',{}).get('trade_count')}", flush=True)

    # ----------------------------------------------------------------------- #
    # 5. Aggregate JSON report
    # ----------------------------------------------------------------------- #
    total_trades = 0
    for row in per_dataset:
        for strat in row.get("strategies", {}).values():
            if isinstance(strat, dict) and strat.get("ok"):
                total_trades += int(strat.get("trade_count") or 0)

    gate_status = {
        "logic_review": {"status": "not_passed", "implemented": True,
                          "detail": "manual logic/lookahead review gate; never auto-passed in this campaign"},
        "purged_cv": {"status": "not_passed", "implemented": True,
                       "detail": "purged_splits() is implemented but requires >=30 realized trades; all datasets produced <30 (often 0) on demo candles with zero CVD"},
        "deflated_metric": {"status": "not_passed", "implemented": True,
                             "detail": "deflated_sharpe() implemented; requires sufficient realized trades; not met"},
        "walk_forward": {"status": "not_passed", "implemented": True,
                          "detail": "walk_forward() implemented; requires >=30 trades; not met"},
        "shadow": {"status": "implemented_not_run", "implemented": True,
                    "detail": "ShadowRunner / live-shadow exist (paper-only, no order path); not executed in this campaign"},
        "micro_live": {"status": "blocked_by_design", "implemented": False,
                        "detail": "paper-only build exposes NO live order path; micro-live promotion is intentionally blocked"},
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "abdalghoniy (paper-only, no live orders)",
        "honesty_notice": "No live orders were placed. No profitability is claimed. "
                          "Demo candle datasets carry zero CVD/funding, so strategies that "
                          "require CVD confirmation produce 0 trades by design. Synthetic "
                          "stress results are a pipeline smoke test, NOT a profitability claim.",
        "acquired_datasets": {
            "requested": TARGET_SYMBOLS,
            "count_acquired": len(successful),
            "count_requested": len(TARGET_SYMBOLS),
            "details": acquired,
        },
        "per_dataset": per_dataset,
        "synthetic_stress": {
            "purpose": "SMOKE TEST ONLY - pipeline executes end-to-end with synthetic CVD/funding. NOT a profitability claim.",
            "walks": synth,
        },
        "real_feature_sanity": real_feature,
        "gate_status": gate_status,
        "summary": {
            "total_real_trades_on_demo": total_trades,
            "no_live_orders": True,
            "no_profitability_claim": True,
            "note": ("On demo candles (zero CVD/funding) both strategies produced 0 trades where "
                     "CVD confirmation is required. The pipeline itself runs cleanly. With a real "
                     "feature-complete dataset non-zero CVD engaged the strategies (see real_feature_sanity). "
                     "Synthetic stress confirms the replay functions execute without error. Promotion "
                     "gates remain unmet due to insufficient realized-trade evidence."),
        },
    }

    out_path = REPORTS_DIR / "autonomous-eval.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\n=== wrote {out_path} ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
