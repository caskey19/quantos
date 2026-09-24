# Risk policy

Limits ship in `config/risk_limits.yml`. The strategy package cannot write that file. The risk engine is a pure function of an intent, a frozen limit set, and a snapshot.

Checked before any broker call: size, notional, gross, net, symbol, sector, position count, order frequency, turnover, daily loss, weekly loss, drawdown, estimated slippage, spread, leverage, concentration, session clock when enforcement is on, dollar volume, participation, price band, stale quote, duplicate client id, abnormal return, broker connectivity, reconciliation freshness, and data trust.

A request larger than the share or notional cap is scaled down. It is not scaled up. Other failed checks reject the order.

## Kill switches

Reasons: manual, risk, market data, broker, strategy anomaly, model drift, loss limit, unexpected position, reconciliation.

Actions: stop new orders, cancel outstanding orders, or allow reduce-only orders. The engine does not submit a liquidation.

Reset is an operator method. Automated loss and data paths must not call it.

## Reconciliation

Cash, equity, and position quantity are compared with a one-dollar tolerance by default. A mismatch trips the reconciliation kill switch and stops new orders.
