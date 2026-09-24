"""Choose a broker without ever constructing live and paper clients together."""

from __future__ import annotations

from quantos.brokers.alpaca import AlpacaBroker
from quantos.brokers.port import BrokerError
from quantos.brokers.simulated import SimulatedBroker
from quantos.settings import Settings


def build_broker(settings: Settings) -> SimulatedBroker | AlpacaBroker:
    if settings.trading_mode == "live":
        raise BrokerError("Live broker construction is refused by the order router until operator unlock")
    if settings.trading_mode == "shadow":
        broker = SimulatedBroker()
        broker.name = "shadow-quotes-only"
        return broker
    if settings.paper_key and settings.paper_secret:
        return AlpacaBroker(settings, paper=True)
    return SimulatedBroker()
