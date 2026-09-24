"""Order pipeline. Persist, risk, then broker. A retry reuses the client order id."""

from __future__ import annotations

from quantos.brokers.port import BrokerTimeout
from quantos.brokers.simulated import SimulatedBroker
from quantos.contracts.models import (
    ALLOWED_TRANSITIONS,
    AccountView,
    KillReason,
    OrderIntent,
    OrderState,
    PositionView,
    Side,
)
from quantos.persistence.store import OpsStore
from quantos.risk.engine import RiskLimits, RiskSnapshot, evaluate_order
from quantos.risk.killswitch import KillSwitch
from quantos.settings import Settings


class PipelineError(RuntimeError):
    pass


class OrderPipeline:
    def __init__(
        self,
        store: OpsStore,
        broker: SimulatedBroker,
        limits: RiskLimits,
        kill: KillSwitch,
        settings: Settings,
    ) -> None:
        self.store = store
        self.broker = broker
        self.limits = limits
        self.kill = kill
        self.settings = settings
        self.blocked: list[dict] = []

    def submit(self, intent: OrderIntent, snap: RiskSnapshot) -> dict:
        if self.settings.trading_mode == "live":
            raise PipelineError("Live submission is disabled")
        existing = self.store.get_order(intent.client_order_id)
        if existing is not None:
            return self._retry(intent, existing)

        if self.settings.trading_mode == "shadow":
            return self._shadow(intent, snap)

        self.store.save_order(intent.client_order_id, intent.model_dump(mode="json"), OrderState.CREATED.value)
        block = self.kill.blocks(intent, _position_qty(snap, intent.symbol))
        if block:
            self._reject(intent, block)
            return {"state": OrderState.REJECTED.value, "reasons": [block], "client_order_id": intent.client_order_id}

        decision = evaluate_order(intent, self.limits, snap)
        if not decision.approved:
            self._reject(intent, "; ".join(decision.reasons))
            self.blocked.append(
                {"client_order_id": intent.client_order_id, "reasons": decision.reasons, "checks": decision.checks}
            )
            return {
                "state": OrderState.REJECTED.value,
                "reasons": decision.reasons,
                "checks": decision.checks,
                "client_order_id": intent.client_order_id,
            }

        sized = intent.model_copy(update={"qty": decision.approved_qty})
        self._move(intent.client_order_id, OrderState.RISK_APPROVED, "risk approved")
        self._move(intent.client_order_id, OrderState.SUBMITTED, "persist before broker")
        try:
            ack = self.broker.submit(sized)
        except BrokerTimeout:
            self._move(intent.client_order_id, OrderState.RECONCILIATION_REQUIRED, "timeout after submit")
            self.kill.trip(KillReason.RECONCILIATION, "timeout after submit")
            return {
                "state": OrderState.RECONCILIATION_REQUIRED.value,
                "client_order_id": intent.client_order_id,
            }
        return self._record_ack(sized, ack)

    def _retry(self, intent: OrderIntent, existing: dict) -> dict:
        state = OrderState(existing["state"])
        if state in {OrderState.SUBMITTED, OrderState.RECONCILIATION_REQUIRED, OrderState.ACKNOWLEDGED}:
            ack = self.broker.submit(intent)
            return self._record_ack(intent, ack)
        return existing

    def _shadow(self, intent: OrderIntent, snap: RiskSnapshot) -> dict:
        decision = evaluate_order(intent, self.limits, snap)
        quote = self.broker.quote(intent.symbol)
        if quote is None:
            available = snap.price
            spread = snap.spread_bps
        else:
            available = quote.ask if intent.side == Side.BUY else quote.bid
            mid = (quote.ask + quote.bid) / 2
            spread = ((quote.ask - quote.bid) / mid * 10_000) if mid else 0
        record = {
            "client_order_id": intent.client_order_id,
            "sent_to_broker": False,
            "approved": decision.approved,
            "reasons": decision.reasons,
            "expected_entry": intent.reference_price,
            "available_price": available,
            "expected_spread_bps": intent.expected_spread_bps,
            "observed_spread_bps": spread,
            "expected_slippage_bps": intent.expected_slippage_bps,
            "observed_slippage_bps": abs(available - intent.reference_price) / intent.reference_price * 10_000
            if intent.reference_price
            else 0,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "qty": decision.approved_qty,
            "checks": decision.checks,
        }
        self.store.save_shadow(intent.client_order_id, record)
        return record

    def _record_ack(self, intent: OrderIntent, ack: dict) -> dict:
        state = str(ack.get("state", OrderState.ACKNOWLEDGED.value))
        current = OrderState(self.store.get_order(intent.client_order_id)["state"])
        target = OrderState(state)
        if target != current and target in ALLOWED_TRANSITIONS.get(current, set()):
            self._move(intent.client_order_id, target, "broker ack")
        fill_id = ack.get("fill_id")
        if fill_id:
            fresh = self.store.record_fill(fill_id, {**ack, "client_order_id": intent.client_order_id})
            if fresh:
                self.store.save_audit(
                    intent.client_order_id,
                    {
                        "strategy": intent.strategy,
                        "strategy_version": intent.strategy_version,
                        "symbol": intent.symbol,
                        "side": intent.side.value,
                        "reason": intent.reason_code,
                        "signal_strength": intent.signal_strength,
                        "requested_qty": intent.qty,
                        "fill_price": ack.get("price"),
                        "expected_spread_bps": intent.expected_spread_bps,
                        "expected_slippage_bps": intent.expected_slippage_bps,
                        "correlation_id": intent.correlation_id,
                    },
                )
                for position in self.broker.positions():
                    self.store.upsert_position(position.symbol, position.qty, position.avg_price, position.sector)
                account = self.broker.account()
                self.store.update_account(
                    cash=account.cash,
                    equity=account.equity,
                    peak_equity=account.peak_equity,
                )
        ack["client_order_id"] = intent.client_order_id
        return ack

    def _reject(self, intent: OrderIntent, detail: str) -> None:
        current = OrderState(self.store.get_order(intent.client_order_id)["state"])
        if OrderState.REJECTED in ALLOWED_TRANSITIONS.get(current, set()):
            self._move(intent.client_order_id, OrderState.REJECTED, detail)

    def _move(self, client_order_id: str, target: OrderState, detail: str) -> None:
        current = OrderState(self.store.get_order(client_order_id)["state"])
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            raise PipelineError(f"illegal transition {current} -> {target}")
        self.store.transition(client_order_id, target.value, detail)


def _position_qty(snap: RiskSnapshot, symbol: str) -> float:
    for position in snap.positions:
        if position.symbol == symbol:
            return position.qty
    return 0.0


def reconcile(internal: AccountView, broker: AccountView, positions_internal: list[PositionView], positions_broker: list[PositionView], tolerance: float) -> list[str]:
    issues: list[str] = []
    if abs(internal.cash - broker.cash) > tolerance:
        issues.append(f"cash mismatch internal={internal.cash} broker={broker.cash}")
    if abs(internal.equity - broker.equity) > tolerance:
        issues.append(f"equity mismatch internal={internal.equity} broker={broker.equity}")
    internal_map = {item.symbol: item.qty for item in positions_internal}
    broker_map = {item.symbol: item.qty for item in positions_broker}
    symbols = set(internal_map) | set(broker_map)
    for symbol in symbols:
        if abs(internal_map.get(symbol, 0) - broker_map.get(symbol, 0)) > tolerance:
            issues.append(f"position mismatch {symbol}")
    return issues
