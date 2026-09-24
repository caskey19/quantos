"""In-process paper broker. Idempotent on client order id. No network."""

from __future__ import annotations

from datetime import datetime, timezone

from quantos.brokers.port import BrokerTimeout
from quantos.contracts.models import AccountView, OrderIntent, OrderState, PositionView, Quote, Side


class SimulatedBroker:
    name = "simulated-paper"
    paper = True

    def __init__(self, equity: float = 100_000) -> None:
        self.cash = equity
        self._positions: dict[str, PositionView] = {}
        self._orders: dict[str, dict] = {}
        self._quotes: dict[str, Quote] = {}
        self.connected_flag = True
        self.fail_next_submit = False
        self.timeout_next_submit = False
        self.submit_calls: list[str] = []
        self.peak = equity

    def set_quote(self, quote: Quote) -> None:
        self._quotes[quote.symbol] = quote

    def account(self) -> AccountView:
        gross = sum(abs(item.qty * item.market_price) for item in self._positions.values())
        net = sum(item.qty * item.market_price for item in self._positions.values())
        equity = self.cash + net
        self.peak = max(self.peak, equity)
        return AccountView(
            equity=equity,
            cash=self.cash,
            buying_power=max(self.cash, 0),
            gross_exposure=gross,
            net_exposure=net,
            peak_equity=self.peak,
            total_pnl=equity - 100_000,
            drawdown=(self.peak - equity) / self.peak if self.peak else 0,
        )

    def positions(self) -> list[PositionView]:
        return list(self._positions.values())

    def open_orders(self) -> list[dict]:
        return [row for row in self._orders.values() if row["state"] not in {"FILLED", "CANCELLED", "REJECTED"}]

    def submit(self, intent: OrderIntent) -> dict:
        self.submit_calls.append(intent.client_order_id)
        if not self.connected_flag:
            raise BrokerTimeout("broker disconnected")
        existing = self._orders.get(intent.client_order_id)
        if existing is not None:
            return existing
        if self.timeout_next_submit:
            self.timeout_next_submit = False
            self._orders[intent.client_order_id] = {
                "client_order_id": intent.client_order_id,
                "state": OrderState.SUBMITTED.value,
                "symbol": intent.symbol,
                "qty": intent.qty,
                "side": intent.side.value,
                "uncertain": True,
            }
            raise BrokerTimeout("timeout after the broker may have accepted the order")
        if self.fail_next_submit:
            self.fail_next_submit = False
            row = {
                "client_order_id": intent.client_order_id,
                "state": OrderState.REJECTED.value,
                "symbol": intent.symbol,
                "qty": 0,
                "reason": "broker rejected",
            }
            self._orders[intent.client_order_id] = row
            return row
        quote = self._quotes.get(intent.symbol)
        price = intent.reference_price or (quote.ask if intent.side == Side.BUY else quote.bid if quote else 0)
        if intent.side == Side.BUY and quote is not None:
            price = quote.ask
        elif intent.side == Side.SELL and quote is not None:
            price = quote.bid
        row = {
            "client_order_id": intent.client_order_id,
            "state": OrderState.FILLED.value,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "qty": intent.qty,
            "price": price,
            "fill_id": f"fill-{intent.client_order_id}",
            "filled_at": datetime.now(timezone.utc).isoformat(),
        }
        self._orders[intent.client_order_id] = row
        self._apply_fill(intent, price)
        return row

    def _apply_fill(self, intent: OrderIntent, price: float) -> None:
        signed = intent.qty if intent.side == Side.BUY else -intent.qty
        current = self._positions.get(intent.symbol)
        qty = (current.qty if current else 0) + signed
        if abs(qty) < 1e-9:
            self._positions.pop(intent.symbol, None)
        else:
            self._positions[intent.symbol] = PositionView(
                symbol=intent.symbol,
                qty=qty,
                avg_price=price,
                sector=intent.sector,
                market_price=price,
                notional=qty * price,
            )
        self.cash -= signed * price

    def modify(self, client_order_id: str, qty: float) -> dict:
        row = self._orders[client_order_id]
        row["qty"] = qty
        return row

    def cancel(self, client_order_id: str) -> dict:
        row = self._orders.get(client_order_id)
        if row is None:
            return {"client_order_id": client_order_id, "state": OrderState.CANCELLED.value}
        if row["state"] == OrderState.FILLED.value:
            return row
        row["state"] = OrderState.CANCELLED.value
        return row

    def quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(symbol)

    def clock(self) -> dict:
        return {"is_open": True, "timestamp": datetime.now(timezone.utc).isoformat()}

    def assets(self) -> list[str]:
        return sorted(self._quotes)

    def connected(self) -> bool:
        return self.connected_flag

    def duplicate_fill(self, client_order_id: str) -> dict:
        return self._orders[client_order_id]
