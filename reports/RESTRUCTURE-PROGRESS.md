# ABDALGHONIY — Orderflow Restructure Progress Report

Status: research infrastructure implemented; validation gates still blocked (honest, not faked).

## What changed this session (committed to hernanda-git/abdalghoniy)

1. Canonical event contracts + durable idempotent store (`events.py`, `store.py`).
2. Public-wallet intelligence: scoring (`wallet_score.py`), consensus (`wallet_consensus.py`), copyability (`copyability.py`), catalog ingestion (`wallets.py`).
3. Regime engine (`regime.py`) + alpha arbitration (`arbitration.py`) requiring agreement and cost-edge before any proposal.
4. Auction-market orderflow strategy from the Chris Kmer breakdown: `orderflow.py` implements the three pillars (environment / location / confirmation). Wired into the replay engine as `--strategy orderflow` and covered by tests.
5. Evaluation ladder hardened: `evaluation.py` adds walk-forward OOS, reproducible random-entry control, and deflated Sharpe. `promotion.py` gates any live promotion behind immutable evidence (positive OOS expectancy, positive lower bound, positive control uplift).
6. Runtime safety telemetry: `runtime_safety.py` exposes armed/halted/partition state from a durable store; dashboard `/api/status` now reports `runtime_state_available` from that store instead of a static paper stub.
7. Rate-limit cooldown hardened on the public market bus (`multi_exchange.py`) so a 429 storm does not hammer the venue.
8. `$10` default notional cap (`config.yaml`): `max_position_notional=10`, `max_leverage=3`, `max_drawdown=0.03`.

All changes are research-only. The system remains `paper` mode; `live_orders_enabled=false`.

## Chris Kmer adaptation (no fabricated edge)

The breakdown describes: environment (higher-TF structure + GEX), location (Fib 0.705/0.788/0.886 around value area), confirmation (absorption + delta dominance shift), execution (stop beyond failed test, trail). We implemented it as pure functions in `orderflow.py`:

- Environment: value-up / value-down / sideways via split-VWAP drift; volatility regime proxy is realized-range expansion (crypto has no GEX feed; this is documented as an adaptation).
- Location: discount / premium zones from value-area Fibonacci levels; trades avoid the middle.
- Confirmation: absorption requires price extreme + close reversal + CVD delta shift. Without CVD, confirmation is `None` (never forced).

This is the documented adaptation, not a claim of profitability. The engine refused to trade on the current 100-candle demo dataset because no full-pillar agreement appeared, which is the correct conservative behavior.

## Validation gates (honest status)

- Logic review: implemented (no lookahead; signals use only past/present data).
- Purged CV: blocked (0 realized trades).
- Deflated metric: computed structure in place, blocked on sample size.
- Walk-forward: structure in place, blocked on sample size.
- Shadow: public read-only path works, no forward-outcome evidence yet.
- Micro-live: blocked (paper-only by policy; demo `SUSDT-FUTURES` credential exists but is not enabled without your explicit approval).

## Deployed

- Repo: `https://github.com/hernanda-git/abdalghoniy` (all commits pushed).
- Dashboard: `https://ag.warga-digital.com` returns 200, mode paper, tests passing, kill-switch source now reads runtime store.
- Services: `abdalghoniy-dashboard.service` + `abdalghoniy-verify.timer` active.

## What is needed to promote (no shortcuts)

- A real, independent dataset with public fill CVD + historical funding for several symbols/windows (the current 100-candle demo is not enough).
- Run the orderflow + wallet-consensus replays through purged CV, deflated metric, walk-forward, and random-control. If post-fee expectancy with positive lower bound survives, `promotion.py` will accept the evidence; otherwise it stays blocked.
- Only after gates 1–5 pass: enable `SUSDT-FUTURES` demo micro-live with the existing credential, capped and kill-switched.

No live orders were placed. No secrets were committed. No backtest number was claimed as profitable.
