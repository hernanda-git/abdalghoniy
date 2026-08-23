# ABDALGHONIY

Safety-first, paper-only fast-alpha perpetual futures research engine.

The Linux implementation path for this session is `/root/abdalghoniy`. The supplied charter names a Windows path that is not mounted in this environment.

## Safety defaults

- Paper mode is the default.
- No LLM dependency exists in the execution package.
- Every non-reduce-only order requires validation completion, an armed kill-switch, and a hard stop.
- Protective reduce-only orders are preserved when the kill-switch trips.
- Secrets are environment-only.

Run tests with `python3 -m pytest -q`.
