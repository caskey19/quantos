# Broker integration

## Port

`BrokerPort` exposes account, positions, open orders, submit, modify, cancel, quote, clock, assets, and connectivity.

## Simulated paper broker

Default when `APCA_API_KEY_ID` is empty. It fills at the touch stored by the test or the API. It is idempotent on client order id. A one-shot timeout mode records the id and then raises, so a retry cannot double-fill.

## Alpaca

Paper host: `https://paper-api.alpaca.markets` with `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`.

Live host: `https://api.alpaca.markets` with `APCA_LIVE_API_KEY_ID` and `APCA_LIVE_API_SECRET_KEY`.

The process refuses to start if both key sets are present. The paper adapter refuses a base URL that is not the paper host. The live adapter is not constructed by `build_broker`. Live `submit` on the Alpaca class raises. That is intentional until the checklist is completed by hand and a later change explicitly wires limited live. This build does not send live orders.

Paper trading at Alpaca is a simulation. The vendor states it does not model borrow fees. This system models a borrow charge in the backtester instead of trusting paper fills.

Free market data is IEX. It is accepted for plumbing and rejected as the only price in a cost conclusion.

Modify is unimplemented until replace semantics are reconciliation-tested. Cancel on the paper client is present and untested against a live account because no keys are stored here.

## Interactive Brokers

Not implemented. The TWS paper port 7497 and live port 7496 are easy to confuse, and the Gateway needs a daily login. That adapter is a separate safety project.
