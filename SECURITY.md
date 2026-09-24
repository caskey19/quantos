# Security

This is a single-operator local system.

- Secrets stay in the environment or in `secrets/`, which is gitignored. `.env.example` and `.env.live.example` contain empty values.
- Paper and live key names are different. The process exits if both are set.
- The API binds to loopback unless it is inside Docker, where Compose publishes only `127.0.0.1`.
- CORS allows the local workstation origins only.
- Logs pass through `redact` before they are emitted. Keys whose names look like secrets are replaced.
- `POST /api/live/enable` returns 403. It does not write `secrets/live.unlock`.
- There is no account system, no signup, and no public strategy route.
- `scripts/scan_secrets.py` rejects private keys and obvious cloud key shapes.
- `scripts/scan_deps.py` rejects a short banned-name list and runs `pip-audit` when that tool is installed.
- The package tree is scanned for `eval` and `exec`.
- Broker credentials are not written into experiment notes.

The unlock phrase, if you ever create the file yourself, is the constant `UNLOCK_PHRASE` in `quantos.settings`. Creating that file is not sufficient. The checklist must also be entirely true, live keys must be the only keys loaded, and `build_broker` still does not construct a live client in this version.

Least privilege for an Alpaca paper key means trading permission only, and no withdrawal permission exists on that API. Do not reuse a live key for paper tests.
