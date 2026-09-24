# Deployment

Local first. Nothing in this compose file is published on a public interface.

## Requirements

Python 3.11 or newer, Node 22 for the workstation, Docker if you want Postgres.

## Local paper process

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:TRADING_MODE = "paper"
python -m quantos.api
```

Copy `.env.example` to `.env` only when you add paper keys. Do not commit `.env`.

Health: `GET http://127.0.0.1:8000/api/health`

## Tests

`pytest`

Secret scan: `python scripts/scan_secrets.py`

Dependency name scan: `python scripts/scan_deps.py`

## Docker

```powershell
docker compose up --build
```

Postgres 16 is the operational database. The API image installs the `postgres` extra. The web dev server is bound through `127.0.0.1:5173`.

Startup creates tables with SQLAlchemy metadata. `migrations/001_init.sql` is the reviewed PostgreSQL sketch of the same tables.

## Backup

`powershell -File scripts/backup.ps1` copies `data/` into `backups/<timestamp>/`.

`powershell -File scripts/restore.ps1 -Stamp <timestamp>` copies it back. Stop the API first.

## Environment checks

`TRADING_MODE` must be `paper` or `shadow` for a normal boot. `live` fails closed. Binding a non-loopback host fails unless `QUANTOS_IN_DOCKER=1`.
