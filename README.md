# ABDALGHONIY

Safety-first, paper-only fast-alpha perpetual futures research engine.

The Linux implementation path for this session is `/root/abdalghoniy`. The supplied charter names a Windows path that is not mounted in this environment.

## Safety defaults

- Paper mode is the default.
- No LLM dependency exists in the execution package.
- Every non-reduce-only order requires validation completion, an armed kill-switch, and a hard stop.
- Protective reduce-only orders are preserved when the kill-switch trips.
- Secrets are environment-only.

Run tests with `python3 -m pytest -q`. Run the paper-only composition root with `python3 -m abdalghoniy --status`. A replay uses public demo candles by default or an explicitly supplied CSV and writes a structured report:

```bash
python3 -m abdalghoniy replay --symbol BTCUSDT --interval 1m
python3 -m abdalghoniy report --latest
python3 -m abdalghoniy live-shadow --symbol BTCUSDT --iterations 10 --sleep 60 --event-path /var/tmp/abdalghoniy-shadow.jsonl
```

`live-shadow` polls public Bitget `SUSDT-FUTURES` demo candles only. It records raw and normalized events, reports stale or duplicate data, and always reports `would_orders: 0`. It does not load credentials and has no order endpoint.

When `--input` is omitted, replay fetches public Bitget `SUSDT-FUTURES` demo candles and stores the ignored CSV under `data/`. An existing CSV can be supplied with `--input` for reproducible offline replay.

## Monitoring deployment

The paper-only dashboard is deployed at [ag.warga-digital.com](https://ag.warga-digital.com/). It exposes only health, public market data, safety state, validation state, and reports. It does not expose credentials, order controls, or live trading.

On the VPS:

- `abdalghoniy-dashboard.service` serves the dashboard on `127.0.0.1:8787` as the dedicated non-root `abdalghoniy-dashboard` user through a read-only bind mount.
- `abdalghoniy-verify.timer` runs pytest, Python compilation, the frontend build, and a local health-schema smoke test every 15 minutes. It records Jakarta evaluation time, commit, and per-check results in the ignored status marker.
- Nginx terminates HTTPS for `ag.warga-digital.com` using a Let's Encrypt certificate.

The project remains `paper` mode. Missing validation evidence, live shadow data, exchange credentials, venue behavior drills, and micro-live approval are intentionally surfaced as blocked, not hidden.
