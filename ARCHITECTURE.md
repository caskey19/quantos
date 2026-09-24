# Architecture

## Path

Market data becomes features, then a market-state snapshot, then strategy targets, then order intents, then a portfolio view, then the risk engine, then the execution pipeline, then a broker port.

Research, machine learning, and agents read artifacts. They do not call `BrokerPort.submit`.

## Packages

| Package | Responsibility |
| --- | --- |
| contracts | Types and the order state machine |
| data | Calendar, immutable parquet, integrity, corporate actions, stream supervisor |
| features | Past-only reversal residual |
| market_state | Volatility, trend, dispersion, breadth. Scalar never exceeds 1 |
| strategy | Target weights for the reversal program |
| signal | Targets to order intents |
| portfolio | Gross and net exposure |
| risk | Hard limits and kill switches |
| execution | Persist, risk, submit, reconcile |
| brokers | Simulated paper broker and an Alpaca paper adapter |
| persistence | Orders, fills, experiments |
| research | Sealed window, metrics, synthetic panel, study |
| ml | Unpromoted linear baseline |
| agents | Memos and the skeptic veto |
| monitoring | Structured logs and process health |
| api | Local FastAPI process |

## Processes

The API process is the trading process. The study is a batch command. An LLM is not called. If one is added later, it stays in the research process.

## Clocks

Session dates use the NYSE calendar in `quantos.data.calendar`. Research timestamps for a close decision are 20:00 UTC on that session date, which is after the cash close. Fills are scheduled on a later session. The backtester drops any order whose signal session is not strictly before the fill session.
