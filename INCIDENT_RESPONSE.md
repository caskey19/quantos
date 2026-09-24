# Incident response

## Order may have been sent twice

1. Trip the manual kill switch.
2. Compare `client_order_id` rows in the operational store with the broker's open orders.
3. A timeout path is supposed to land in `RECONCILIATION_REQUIRED` and refuse a second id. If two broker orders share one client id, cancel the extra only after you can see both.
4. Do not enable live mode while investigating.

## Positions do not match

1. Call reconcile.
2. Leave the kill switch tripped.
3. The difference between internal cash and broker cash above the tolerance is an incident, not a rounding preference to hide.

## Market data stops

The stream supervisor marks the feed stale. Risk rejects stale quotes when a snapshot carries the age. Trip `market_data` if the workstation still looks healthy and the feed is not.

## Secret exposure

1. Revoke the key at the broker.
2. Remove it from the environment.
3. Run `python scripts/scan_secrets.py`.
4. Do not commit the file that contained it.

## Live mode suspected

`GET /api/session` must show `live_locked: true` in this build. If `live_submission_allowed` is true, stop the process. That state is not reachable with the shipped checklist.
