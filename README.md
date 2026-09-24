# quant-os

Private quantitative research and execution system for one operator. It studies a narrow US-equity hypothesis and refuses to trade live unless every gate in `LIVE_TRADING_CHECKLIST.md` is completed by hand.

No result in this repository is a claim of profit. The first study is a synthetic methodology run. Its promotion state is `REJECTED` because market data was not used.

## Run tests

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
python -m quantos.research.study
```

## Paper API

```powershell
$env:TRADING_MODE = "paper"
python -m quantos.api
```

The API binds to `127.0.0.1:8000`. The workstation is `apps/web` (`npm install`, `npm run dev`).

Docker Compose publishes Postgres, the API, and the web app on loopback only. Inside the container the API binds all interfaces because the published port is already limited to `127.0.0.1`.

## Live trading

Live submission is disabled. `POST /api/live/enable` returns 403 and does not create an unlock file. See `SECURITY.md` and `LIVE_TRADING_CHECKLIST.md`.

## Layout

Python packages live under `packages/quantos`. The trading path is data, features, market state, strategy, signal, portfolio, risk, execution, broker. Research agents are not on that path.
