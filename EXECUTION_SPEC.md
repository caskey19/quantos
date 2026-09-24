# Execution specification

## When a fill may happen

A signal on session D may fill on a later session only. The backtester enforces `signal_session < fill_session`.

## Models

Optimistic: next open plus 1 basis point, no commission.

Expected: next open plus half the quoted spread, plus participation slippage capped at 20 basis points of price, plus a 0.000166 per-share sell fee. This fee is an assumption for stress testing, not a legal schedule.

Stress: the worse of the next open and that session's close, plus the full spread, plus extra slippage, plus 0.005 per share. Participation above 5 percent of dollar volume fills half. Participation above 20 percent misses. Shorts pay 1 basis point of notional per session as a borrow assumption.

A strategy is not accepted because the optimistic model looks good.

## Orders

Market orders are the research path. Limit orders fill only if the bar trades through the limit. Stop orders are rejected when the stop is not touched. Stress limit fills do not receive a price improvement beyond the limit.

## Idempotency

The client order id is stored before the broker call. A timeout after submit moves the order to `RECONCILIATION_REQUIRED`, trips the kill switch, and a retry uses the same id. The simulated broker returns the original row instead of creating a second order. A repeated fill id is ignored.

## Shadow

Shadow mode records the price that was available and does not call submit. The record includes expected spread, observed spread, and the gap between the reference price and the touch.
