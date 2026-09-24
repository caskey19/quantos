# Runbook

## Start paper mode

1. Confirm `TRADING_MODE=paper`.
2. Start `python -m quantos.api`.
3. Open `http://127.0.0.1:8000/api/health` and confirm `"mode": "paper"`.
4. Start the workstation with `npm run dev` inside `apps/web`.

## Stop new orders

`POST /api/kill` with `{"reason": "manual", "detail": "operator"}`.

The action stops new risk. It does not liquidate.

## Data looks wrong

Read `GET /api/data-health`. If `trustworthy` is false, do not treat scanner rows or backtest figures as market evidence. The synthetic study is labeled synthetic.

## Broker state disagrees

`POST /api/reconcile`. A mismatch trips the reconciliation kill switch. Investigate before resetting anything. This build does not expose an API reset.

## Restart with positions

The operational store reloads positions into the simulated broker on startup. Confirm `GET /api/positions` before submitting anything new.

## Study

`python -m quantos.research.study` rewrites `research/results/reversal_study.json`. Read `hypothesis_status` before reading a Sharpe.
