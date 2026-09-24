"""Broker port. Live and paper credentials are not interchangeable."""

from __future__ import annotations

from typing import Protocol

from quantos.contracts.models import AccountView, OrderIntent, PositionView, Quote


class BrokerError(RuntimeError):
    pass


class BrokerTimeout(BrokerError):
    pass


class BrokerPort(Protocol):
    name: str
    paper: bool

    def account(self) -> AccountView: ...

    def positions(self) -> list[PositionView]: ...

    def open_orders(self) -> list[dict]: ...

    def submit(self, intent: OrderIntent) -> dict: ...

    def modify(self, client_order_id: str, qty: float) -> dict: ...

    def cancel(self, client_order_id: str) -> dict: ...

    def quote(self, symbol: str) -> Quote | None: ...

    def clock(self) -> dict: ...

    def assets(self) -> list[str]: ...

    def connected(self) -> bool: ...
