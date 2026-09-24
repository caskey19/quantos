"""Signal layer. Turns targets into order intents. It does not talk to a broker."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from quantos.contracts.models import OrderIntent, TargetWeight
from quantos.data.calendar import next_session
from quantos.strategy.reversal import STRATEGY_NAME, STRATEGY_VERSION


def intents_from_targets(
    targets: list[TargetWeight],
    prices: dict[str, float],
    decision_session: date,
    correlation_id: str,
) -> list[OrderIntent]:
    scheduled = next_session(decision_session)
    intents: list[OrderIntent] = []
    for target in targets:
        price = prices.get(target.symbol, 0)
        if price <= 0:
            continue
        intents.append(
            OrderIntent(
                client_order_id=f"qos_{uuid4().hex}",
                symbol=target.symbol,
                side=target.side,
                qty=target.target_notional / price,
                signal_ts=datetime(decision_session.year, decision_session.month, decision_session.day, 20, 0, tzinfo=timezone.utc),
                decision_session=decision_session,
                scheduled_session=scheduled,
                strategy=STRATEGY_NAME,
                strategy_version=STRATEGY_VERSION,
                reason_code=target.reason_code,
                signal_strength=target.signal_strength,
                sector=target.sector,
                correlation_id=correlation_id,
                reference_price=price,
                expected_holding_sessions=target.hold_sessions,
            )
        )
    return intents
