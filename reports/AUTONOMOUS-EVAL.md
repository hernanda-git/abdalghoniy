# ABDALGHONIY — Autonomous Evaluation Campaign

**Generated:** 2026-08-25 (UTC) · **Engine:** `abdalghoniy` (paper-only, no live orders)
**Honesty banner:** No live orders were placed. No profitability is claimed anywhere in this
report. All numbers below are real outputs of the engine on real or explicitly-synthetic data.

---

## 1. What was done

1. **Acquisition** — Called `fetch_demo_candles(symbol, "1m", limit=1000)` for the five target
   symbols with exponential-backoff retry (6 attempts) and cached each CSV under `data/`.
2. **Replay** — For every acquired dataset, ran **both** strategies (`orderflow`,
   `counter_trend`) through the **production CLI** (`python -m abdalghoniy replay`) so the exact
   shipping code path was exercised. Captured `trade_count`, `net_pnl`, `gross`, `fees`, the
   validation payload, and whether CVD/funding were non-zero.
3. **Synthetic stress / smoke test** — Generated 3 independent random-walk price series
   (1000 bars each) with **synthetic** CVD and funding, ran both replays, and recorded trade
   counts + net expectancy. This only proves the pipeline executes end-to-end. **It is NOT a
   profitability claim.**
4. **Real-feature sanity** — Replayed the cached real `feature-complete` dataset (1000 rows with
   non-zero CVD/funding) to confirm the strategies actually engage when features are real.

---

## 2. Acquired datasets (honest status)

| Symbol | Acquired | Candles | Notes |
|--------|----------|---------|-------|
| BTCUSDT | ✅ | 1000 | cached → `data/btcusdt_1m.csv` |
| ETHUSDT | ✅ | 1000 | cached → `data/ethusdt_1m.csv` |
| XRPUSDT | ✅ | 1000 | cached → `data/xrpusdt_1m.csv` |
| SOLUSDT | ❌ | 0 | HTTP 400 — **not listed** on SUSDT-FUTURES demo venue |
| DOGEUSDT | ❌ | 0 | HTTP 400 — **not listed** on SUSDT-FUTURES demo venue |

**Venue reality (verified against `/api/v2/mix/market/contracts?productType=SUSDT-FUTURES`):**
the public demo venue lists only **3 contracts** — `SBTCSUSDT`, `SETHSUSDT`, `SXRPSUSDT`.
SOLUSDT/DOGEUSDT are simply unavailable there. This is a data-availability limit, **not** a rate
limit and **not** an engine bug. It also means genuinely independent multi-symbol evidence on this
venue is capped at 3 symbols.

---

## 3. Per-dataset replay results (real demo candles)

Demo candles carry **empty `cvd_change` / `funding_bps`** (loaded as 0). Both strategies require
CVD confirmation, so they correctly produced **0 trades** on every demo dataset:

| Symbol | Strategy | Trades | Net PnL | CVD non-zero |
|--------|----------|--------|---------|--------------|
| BTCUSDT | orderflow | 0 | 0 | 0 |
| BTCUSDT | counter_trend | 0 | 0 | 0 |
| ETHUSDT | orderflow | 0 | 0 | 0 |
| ETHUSDT | counter_trend | 0 | 0 | 0 |
| XRPUSDT | orderflow | 0 | 0 | 0 |
| XRPUSDT | counter_trend | 0 | 0 | 0 |

**This 0-trade result is expected and honest.** The validation ladder returns
`status: insufficient_evidence` (trade_count < 30) and every gate stays `not_passed`.

---

## 4. Synthetic stress / smoke test (NOT a profitability claim)

Random-walk data with synthetic CVD/funding; purpose = prove the replay path runs without error.

| Walk (seed) | orderflow trades | of net exp. | counter_trend trades | ct net exp. |
|-------------|------------------|------------|----------------------|-------------|
| 101 | 23 | -0.050 | 58 | +0.069 |
| 202 | 24 | -0.114 | 45 | -0.130 |
| 303 | 23 | -0.137 | 48 | +0.036 |

Net expectancy fluctuates around zero with sign-flipping across seeds — exactly what random data
should do. **Do not read any edge into these numbers.** They only confirm the engine executes.

---

## 5. Real-feature sanity replay (non-zero CVD)

Dataset: `data/sbtcsusdt_1m_feature_complete_1000.csv` (1000 rows, real CVD/funding).

| Strategy | Trades | Net PnL | Note |
|----------|--------|---------|------|
| orderflow | 6 | -0.063 | engaged because CVD was real; still < 30 trades |
| counter_trend | 0 | 0 | no patterns met its thresholds on this sample |

Confirms the strategies **do** fire when real features are supplied; the demo 0-trades are a
feature-data artifact, not a broken engine.

---

## 6. Promotion gate status (honest)

| Gate | Status | Implemented? | Why |
|------|--------|--------------|-----|
| logic_review | not_passed | yes | manual lookahead/logic review; never auto-passed here |
| purged_cv | not_passed | yes | `purged_splits()` exists; needs ≥30 realized trades — unmet |
| deflated_metric | not_passed | yes | `deflated_sharpe()` exists; needs sufficient trades — unmet |
| walk_forward | not_passed | yes | `walk_forward()` exists; needs ≥30 trades — unmet |
| shadow | implemented_not_run | yes | ShadowRunner / live-shadow exist (paper, no order path); not executed |
| micro_live | blocked_by_design | no | paper-only build exposes **no** live order path |

---

## 7. Exactly what is needed to promote

To move a strategy past `research_only` the validation ladder requires all six gates authorized
with non-empty evidence. Concretely, the missing inputs are:

1. **Independent multi-symbol / multi-window data.** Demonstrably separate symbols *and* time
   windows (not overlapping samples). On this public venue only BTC/ETH/XRP exist, so additional
   venues or windows are required for true independence.
2. **Purged cross-validation** on each window (`purged_splits` with purge/embargo) showing the
   edge survives out-of-sample — requires ≥30 *realized* trades per window.
3. **Deflated Sharpe** (`deflated_sharpe`) above the penalty threshold on real returns, not
   synthetic ones.
4. **Walk-forward** validation (`walk_forward`) with stable out-of-sample performance.
5. **Random control** comparison (`random_control`) showing the strategy beats sign-flipped /
   shuffled returns.
6. **Shadow / micro-live** execution — currently blocked by design (paper-only). Requires an
   explicit, separately-authorized live path before any order is placed.

Until ≥30 realized, in-sample-and-out-of-sample trades exist on independent data, **no strategy
in this engine is promoted and no live orders will ever be placed by this build.**

---

## 8. One-paragraph honest summary

The campaign acquired 3 of 5 requested demo datasets (BTC/ETH/XRP, 1000 candles each); SOL and
DOGE could not be fetched because the public Bitget SUSDT-FUTURES demo venue lists only three
contracts (BTC, ETH, XRP) — a genuine data-availability limit, not a rate limit or code bug. On
the acquired demo candles **both strategies produced 0 trades**, which is correct by-design: the
demo feed carries zero CVD/funding and the strategies require CVD confirmation. The engine itself
is healthy — the synthetic stress test executed both replays cleanly (orderflow ~23 trades,
counter_trend ~45–58 trades per random walk, with expectancy flipping sign across seeds, i.e. no
edge), and a real feature-complete dataset (non-zero CVD) engaged orderflow for 6 trades. Every
promotion gate is `not_passed` because realized-trade evidence is far below the ≥30 threshold. No
live orders were placed and no profitability is claimed.
