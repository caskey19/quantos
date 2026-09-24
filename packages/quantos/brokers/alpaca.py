"""Alpaca adapter.

Paper and live use different hosts and different environment variables.
This module refuses to construct a live client unless assert_live_allowed passes.
The Alpaca SDK is imported only inside the live/paper constructor so tests run
without the optional dependency.
"""

from __future__ import annotations

from quantos.brokers.port import BrokerError
from quantos.contracts.models import AccountView, OrderIntent, PositionView, Quote
from quantos.settings import Settings, assert_live_allowed


class AlpacaBroker:
    def __init__(self, settings: Settings, *, paper: bool) -> None:
        if paper and (settings.live_key or settings.live_secret):
            raise BrokerError("Refusing to build a paper adapter while live credentials are loaded")
        if not paper:
            if settings.trading_mode != "live":
                raise BrokerError("Live adapter requested while TRADING_MODE is not live")
            assert_live_allowed(settings)
        self.paper = paper
        self.name = "alpaca-paper" if paper else "alpaca-live"
        self._base = settings.paper_base_url if paper else settings.live_base_url
        key = settings.paper_key if paper else settings.live_key
        secret = settings.paper_secret if paper else settings.live_secret
        if not key or not secret:
            raise BrokerError("Alpaca credentials are not configured")
        if paper and "paper-api" not in self._base:
            raise BrokerError("Paper adapter base URL must be the paper host")
        if not paper and "paper-api" in self._base:
            raise BrokerError("Live adapter base URL must not be the paper host")
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise BrokerError("alpaca-py is not installed") from exc
        self._client = TradingClient(key, secret, paper=paper)
        self._seen: dict[str, dict] = {}

    def account(self) -> AccountView:
        account = self._client.get_account()
        equity = float(account.equity)
        return AccountView(
            equity=equity,
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            peak_equity=equity,
        )

    def positions(self) -> list[PositionView]:
        rows = []
        for position in self._client.get_all_positions():
            qty = float(position.qty)
            price = float(position.current_price)
            rows.append(
                PositionView(
                    symbol=position.symbol,
                    qty=qty,
                    avg_price=float(position.avg_entry_price),
                    market_price=price,
                    notional=qty * price,
                )
            )
        return rows

    def open_orders(self) -> list[dict]:
        return [{"client_order_id": order.client_order_id, "symbol": order.symbol} for order in self._client.get_orders()]

    def submit(self, intent: OrderIntent) -> dict:
        if not self.paper:
            raise BrokerError("Live submit is not wired until the operator checklist is complete in-process")
        existing = self._seen.get(intent.client_order_id)
        if existing is not None:
            return existing
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        side = OrderSide.BUY if intent.side.value == "buy" else OrderSide.SELL
        if intent.order_type.value == "limit":
            request = LimitOrderRequest(
                symbol=intent.symbol,
                qty=intent.qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                limit_price=intent.limit_price,
                client_order_id=intent.client_order_id,
            )
        else:
            request = MarketOrderRequest(
                symbol=intent.symbol,
                qty=intent.qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                client_order_id=intent.client_order_id,
            )
        order = self._client.submit_order(request)
        row = {
            "client_order_id": intent.client_order_id,
            "broker_order_id": str(order.id),
            "state": str(order.status),
            "symbol": intent.symbol,
            "qty": intent.qty,
        }
        self._seen[intent.client_order_id] = row
        return row

    def modify(self, client_order_id: str, qty: float) -> dict:
        raise BrokerError("Modify is intentionally unavailable until replace semantics are reconciliation-tested")

    def cancel(self, client_order_id: str) -> dict:
        if not self.paper:
            raise BrokerError("Live cancel is disabled")
        self._client.cancel_order_by_client_id(client_order_id)
        return {"client_order_id": client_order_id, "state": "CANCEL_PENDING"}

    def quote(self, symbol: str) -> Quote | None:
        return None

    def clock(self) -> dict:
        clock = self._client.get_clock()
        return {"is_open": bool(clock.is_open), "timestamp": str(clock.timestamp)}

    def assets(self) -> list[str]:
        return []

    def connected(self) -> bool:
        try:
            self._client.get_clock()
            return True
        except Exception:
            return False
