# ABDALGHONIY

Safety-first, paper-only fast-alpha perpetual futures research engine.

The Linux implementation path for this session is `/root/abdalghoniy`. The supplied charter names a Windows path that is not mounted in this environment.

## Safety defaults

- Paper mode is the default.
- No LLM dependency exists in the execution package.
- Every non-reduce-only order requires validation completion, an armed kill-switch, and a hard stop.
- Protective reduce-only orders are preserved when the kill-switch trips.
- Secrets are environment-only.

Run tests with `python3 -m pytest -q`. Run the paper-only composition root with `python3 -m abdalghoniy --status`.

## Monitoring deployment

The paper-only dashboard is deployed at [ag.warga-digital.com](https://ag.warga-digital.com/). It exposes only health, public market data, safety state, validation state, and reports. It does not expose credentials, order controls, or live trading.

On the VPS:

- `abdalghoniy-dashboard.service` serves the dashboard on `127.0.0.1:8787`.
- `abdalghoniy-verify.timer` runs the offline test suite every 15 minutes and updates an ignored status marker.
- Nginx terminates HTTPS for `ag.warga-digital.com` using a Let's Encrypt certificate.

The project remains `paper` mode. Missing validation evidence, live shadow data, exchange credentials, venue behavior drills, and micro-live approval are intentionally surfaced as blocked, not hidden.
