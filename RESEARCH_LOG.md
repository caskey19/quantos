# Research log

Accessed sources are listed in `SOURCE_REGISTRY.md`. This log records what was done with them.

## 2026-09-23 — program selection

The supplied videos are promotional execution tutorials. They contributed a research loop, a forward-test incubation idea, a trade ledger, and a warning not to turn one loss into a permanent rule. They did not contribute a US-equity hypothesis. Profit language in those videos is not evidence.

The first program is liquidity-conditioned short-horizon reversal. It was chosen because the mechanism is published, disputed, and testable at a daily horizon. It was not chosen because a backtest looked good. No market backtest has been accepted.

## Pre-registered grid

Lookback in {1, 5} and hold in {1, 5}. Four trials. Execution models are optimistic, expected, and stress. The stress model is the gate. The sealed window starts 2025-04-01 and is not readable for research.

## 2026-09-23 — synthetic methodology run

Command: `python -m quantos.research.study`.

Artifact: `research/results/reversal_study.json`.

Data version: `synthetic-seed-7-liquid-24-illiquid-6`. Sessions from 2022-01-03 through 2024-06-28. Train window ends and the validation window starts on 2023-07-03. The sealed window was not opened. Trial count: 4. These numbers are validation-window results. They are not market results.

Stress Sharpe by pre-registered cell:

- lookback 1, hold 1: -8.22, 169 trades
- lookback 1, hold 5: -6.84, 459 trades
- lookback 5, hold 1: -12.84, 370 trades
- lookback 5, hold 5: -8.61, 394 trades

The least-bad stress cell is still negative. Deflated Sharpe probability on every stress cell is 0. There is no positive stress plateau.

For contrast, the optimistic model on lookback 1, hold 5 has validation Sharpe 0.51 and 530 trades. The expected model on that same cell has Sharpe 0.24. That optimistic figure is exactly the kind of result the stress gate is there to refuse. It is not a finding about US equities.

The live loss halt, leverage cap, and concentration cap were not applied inside this measurement. Those controls stop a damaged book from continuing, which would censor the rest of the sample. Per-trade notional, the spread gate, and the dollar-volume gate stayed on. The order pipeline used by the API still loads `config/risk_limits.yml` unchanged.

Promotion: `REJECTED`. Hypothesis status: `untested_on_market_data`. The skeptic vetoes because the panel is synthetic and survivorship is unresolved. A negative synthetic stress Sharpe does not prove the market anomaly is absent. It does show that this plant does not survive the stress fill model, and that an optimistic Sharpe would have been a misleading summary.

