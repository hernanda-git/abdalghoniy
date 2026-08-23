# Engineering review and hardening status

## Fixed in this iteration

- Added executable paper-only CLI: `python3 -m abdalghoniy --status`.
- Added authoritative YAML loading with unknown-key rejection and typed fee, slippage, leverage, drawdown, and notional limits.
- Restricted current build to paper mode. `shadow` and `micro_live` fail closed until real adapters and operator approval exist.
- Validation promotion now requires JSON evidence metadata: dataset hash, evaluation time, code hash, and metric for every gate.
- Invalid fee inputs and invalid trade directions are rejected.
- Backtest now aligns funding data and applies the configured funding filter.
- Backtest prevents overlapping positions in the replay path.
- Added bounded account simulator with notional and leverage limits.
- Edge decay blocks new risk while allowing reduce-only exits.
- Daily loss breaker persists state and rolls over using Asia/Jakarta day boundaries.
- Added CLI, adversarial, account, funding, persistence, validation, and dashboard tests.

## Remaining blocked gates

The system is intentionally not declared trading-complete. It still lacks independent evidence for purged CV, deflated performance, walk-forward, shadow mode, and micro-live. No live exchange credentials were supplied, and no live order path is enabled. Profitability remains unproven.
