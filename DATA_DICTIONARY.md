# Data dictionary

## Bar

`symbol`, `session_date` (America/New_York session), `open`, `high`, `low`, `close`, `volume`, `dollar_volume`, optional `bid` and `ask`, `spread_bps`, `sector`, `source`, `adjustment` (`raw`, `split`, or `total_return`), `exchange_ts`, `ingest_ts`, `liquid`.

Raw parquet is content-addressed. A second write of different bytes creates a new file. Adjusted bars are a different dataset.

## Feature

`past_return` is the symbol's close-to-close return over the lookback. `residual` subtracts the cross-sectional mean of that return on the same session. `feature_asof` equals `session_date`. The feature does not use a negative shift.

## Label

`forward_return` lives in `quantos.research.labels` and uses future opens. Strategy code is not allowed to import it.

## Order

`client_order_id` is the idempotency key. `decision_session` is the signal session. `scheduled_session` is the first session that may fill. States are the machine in `quantos.contracts.models`.

## Experiment

Identity, git revision, data version, feature set, parameters, train window, validation window, test window, cost assumptions, metrics, result, notes, and trial count. Rows cannot be deleted through the store API.

## Sealed window

`config/sealed_window.yml`. Research purpose `promotion_review` is the only purpose allowed to read it, and the application does not use that purpose.

## Known bias

Synthetic rows are tagged `source=synthetic`. A free Alpaca asset list is not a point-in-time membership list. Reports must say so.
