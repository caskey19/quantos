# Plan

This file records the approved build. It is the project copy. Live trading stays disabled.

## Decision

Build a single-operator research and execution system at this repository. Specialize in one falsifiable program: liquidity-conditioned short-horizon cross-sectional reversal in liquid US common stocks. Do not treat that program as profitable. The default outcome is rejection when costs, quotes, or untouched data wipe it out.

## Why this program

The holding period is days, so a home Python process is fast enough. The cross-section creates a sample without thin names. The published mechanism is disputed, which makes a null result informative. Prior work says naive reversal profits are often bid-ask bounce and costs. Alpaca can express the orders later. Order-book colocation is out of scope.

Reserve programs, not built: post-earnings drift, then intermediate residual momentum.

Rejected for this operator: intraday order-book trading, crypto bot search, LLM price prediction, borrow-dependent pairs, options volatility premium, and any rule whose only support is a searched backtest.

## Architecture

One process for trading. A separate research path. Strategy code cannot import the broker SDK. Agent code cannot import order submission. Every order is persisted before a network call. Live mode requires `TRADING_MODE=live`, the unlock file, separate live credentials, a completed checklist, and still has no API that can create the unlock file.

PostgreSQL is the operational database in Docker. SQLite is the local default so tests do not need a server. Parquet plus DuckDB hold market data. Raw files are write-once. Redis, Kafka, and Kubernetes are not used.

Alpaca is the first real adapter and is paper-only in this build. The simulated broker is the default when paper keys are absent. IBKR is documented and not implemented.

## Validation

Four pre-registered parameter cells. Three execution models. The sealed window in `config/sealed_window.yml` cannot be read for research. Promotion looks at the stress model, a parameter plateau, and a skeptic veto. The skeptic vetoes anything that is not real market evidence.

## Sequence

Waves A through F land the foundation, data and backtest, the synthetic study, risk and the workstation, agents and scanning, and shadow mode with the live checklist still false.
