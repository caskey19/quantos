"""Deterministic risk gate. Strategy code cannot construct or mutate RiskLimits."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field

from quantos.contracts.models import AccountView, OrderIntent, PositionView, RiskDecision, Side


class RiskLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_equity_reference: float = 100000
    max_shares: float = 500
    max_notional_per_trade: float = 5000
    max_gross_exposure: float = 50000
    max_net_exposure: float = 10000
    max_symbol_notional: float = 5000
    max_sector_notional: float = 15000
    max_open_positions: int = 12
    max_orders_per_day: int = 40
    max_daily_turnover: float = 25000
    max_daily_loss: float = 500
    max_weekly_loss: float = 1500
    max_drawdown_fraction: float = 0.05
    max_estimated_slippage_bps: float = 25
    max_spread_bps: float = 15
    max_leverage: float = 1.0
    max_concentration: float = 0.10
    min_price: float = 5
    max_price: float = 2000
    min_average_dollar_volume: float = 20_000_000
    max_participation: float = 0.01
    max_bar_staleness_seconds: float = 120
    max_abs_return: float = 0.25
    reconciliation_tolerance: float = 1.0
    market_open: str = "09:30"
    market_close: str = "16:00"
    timezone: str = "America/New_York"
    allow_extended_hours: bool = False
    kill_action: str = "stop_new"

    @classmethod
    def from_file(cls, path: Path) -> "RiskLimits":
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(payload)


class RiskSnapshot(BaseModel):
    account: AccountView
    positions: list[PositionView]
    orders_today: int = 0
    turnover_today: float = 0
    price: float
    dollar_volume: float
    spread_bps: float
    estimated_slippage_bps: float
    last_return: float = 0
    quote_age_seconds: float = 0
    broker_connected: bool = True
    reconciliation_ok: bool = True
    data_trustworthy: bool = True
    now: datetime | None = None
    session_date: date | None = None
    known_client_order_ids: set[str] = Field(default_factory=set)
    enforce_market_hours: bool = False


def _within_session(now: datetime, limits: RiskLimits) -> bool:
    zone = ZoneInfo(limits.timezone)
    local = now.astimezone(zone)
    start_h, start_m = (int(part) for part in limits.market_open.split(":"))
    end_h, end_m = (int(part) for part in limits.market_close.split(":"))
    start = time(start_h, start_m)
    end = time(end_h, end_m)
    return start <= local.time() <= end


def evaluate_order(intent: OrderIntent, limits: RiskLimits, snap: RiskSnapshot) -> RiskDecision:
    checks: dict[str, bool] = {}
    reasons: list[str] = []
    price = snap.price
    qty = abs(intent.qty)
    scaled = False
    if price > 0:
        capped = min(qty, limits.max_shares, limits.max_notional_per_trade / price)
        scaled = capped + 1e-9 < qty
        qty = capped
    requested_notional = qty * price

    def fail(name: str, reason: str) -> None:
        checks[name] = False
        reasons.append(reason)

    def ok(name: str) -> None:
        checks[name] = True

    if intent.client_order_id in snap.known_client_order_ids:
        fail("duplicate_order", "duplicate client order id")
    else:
        ok("duplicate_order")

    if price <= 0 or price < limits.min_price or price > limits.max_price:
        fail("price_limit", f"price {price} outside [{limits.min_price}, {limits.max_price}]")
    else:
        ok("price_limit")

    if not snap.data_trustworthy:
        fail("data_trust", "market data is not trustworthy")
    else:
        ok("data_trust")

    if snap.quote_age_seconds > limits.max_bar_staleness_seconds:
        fail("stale_data", "quote is stale")
    else:
        ok("stale_data")

    if abs(snap.last_return) > limits.max_abs_return:
        fail("abnormal_volatility", "bar return exceeds the abnormal-move limit")
    else:
        ok("abnormal_volatility")

    if not snap.broker_connected:
        fail("connectivity", "broker is not connected")
    else:
        ok("connectivity")

    if not snap.reconciliation_ok:
        fail("broker_state", "broker reconciliation is outside tolerance")
    else:
        ok("broker_state")

    if snap.spread_bps > limits.max_spread_bps:
        fail("spread", f"spread {snap.spread_bps:.1f} bps exceeds {limits.max_spread_bps}")
    else:
        ok("spread")

    if snap.estimated_slippage_bps > limits.max_estimated_slippage_bps:
        fail("slippage", "estimated slippage exceeds the limit")
    else:
        ok("slippage")

    if snap.dollar_volume < limits.min_average_dollar_volume:
        fail("liquidity", "dollar volume is below the minimum")
    else:
        ok("liquidity")

    if price > 0 and requested_notional > limits.max_participation * snap.dollar_volume:
        fail("participation", "order is too large relative to observed volume")
    else:
        ok("participation")

    if snap.enforce_market_hours and snap.now is not None and not limits.allow_extended_hours:
        if not _within_session(snap.now, limits):
            fail("market_hours", "outside regular market hours")
        else:
            ok("market_hours")
    else:
        ok("market_hours")

    if snap.account.day_pnl <= -limits.max_daily_loss:
        fail("daily_loss", "daily loss limit reached")
    else:
        ok("daily_loss")

    if snap.account.week_pnl <= -limits.max_weekly_loss:
        fail("weekly_loss", "weekly loss limit reached")
    else:
        ok("weekly_loss")

    if snap.account.peak_equity > 0:
        drawdown = (snap.account.peak_equity - snap.account.equity) / snap.account.peak_equity
    else:
        drawdown = snap.account.drawdown
    if drawdown >= limits.max_drawdown_fraction:
        fail("drawdown", "drawdown limit reached")
    else:
        ok("drawdown")

    if snap.orders_today >= limits.max_orders_per_day:
        fail("order_frequency", "daily order count reached")
    else:
        ok("order_frequency")

    if snap.turnover_today + requested_notional > limits.max_daily_turnover:
        fail("turnover", "daily turnover limit reached")
    else:
        ok("turnover")

    gross = snap.account.gross_exposure
    net = snap.account.net_exposure
    signed = requested_notional if intent.side == Side.BUY else -requested_notional
    position = next((item for item in snap.positions if item.symbol == intent.symbol), None)
    current_notional = position.notional if position else 0.0
    projected_symbol = current_notional + signed
    projected_gross = gross - abs(current_notional) + abs(projected_symbol)
    projected_net = net - current_notional + projected_symbol
    new_position = position is None or abs(position.qty) < 1e-9
    projected_count = len([item for item in snap.positions if abs(item.qty) > 0]) + (1 if new_position else 0)

    equity = max(snap.account.equity, 1.0)
    leverage = projected_gross / equity
    if leverage > limits.max_leverage + 1e-9:
        fail("leverage", "projected leverage exceeds the limit")
    else:
        ok("leverage")

    if abs(projected_gross) > limits.max_gross_exposure:
        fail("gross_exposure", "projected gross exposure exceeds the limit")
    else:
        ok("gross_exposure")

    if abs(projected_net) > limits.max_net_exposure:
        fail("net_exposure", "projected net exposure exceeds the limit")
    else:
        ok("net_exposure")

    if abs(projected_symbol) > limits.max_symbol_notional:
        fail("symbol_exposure", "projected symbol exposure exceeds the limit")
    else:
        ok("symbol_exposure")

    sector_notional = sum(abs(item.notional) for item in snap.positions if item.sector == intent.sector)
    if sector_notional + requested_notional > limits.max_sector_notional:
        fail("sector_exposure", "projected sector exposure exceeds the limit")
    else:
        ok("sector_exposure")

    if new_position and projected_count > limits.max_open_positions:
        fail("open_positions", "open position count exceeds the limit")
    else:
        ok("open_positions")

    if abs(projected_symbol) / equity > limits.max_concentration:
        fail("concentration", "position concentration exceeds the limit")
    else:
        ok("concentration")

    approved_qty = qty
    if approved_qty <= 0:
        fail("size", "approved quantity is zero")
    elif scaled:
        checks["size"] = True
        reasons.append("quantity scaled down to the hard size limit")
    else:
        ok("size")

    hard_failures = [name for name, passed in checks.items() if not passed]
    approved = not hard_failures and approved_qty > 0
    return RiskDecision(
        approved=approved,
        approved_qty=float(approved_qty if approved else 0),
        reasons=reasons,
        checks=checks,
    )
