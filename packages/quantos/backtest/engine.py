"""Event-driven backtest. Fills happen on a later session than the signal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from datetime import datetime, timezone
from uuid import uuid4

from quantos.contracts.models import AccountView, ExecutionModelName, OrderIntent, OrderType, PositionView, Side
from quantos.data.calendar import next_session
from quantos.data.corporate import apply_position_split, cash_dividend
from quantos.risk.engine import RiskLimits, RiskSnapshot, evaluate_order
from quantos.strategy.reversal import STRATEGY_NAME, STRATEGY_VERSION, ReversalStrategy


@dataclass
class OpenPosition:
    symbol: str
    qty: float
    entry_price: float
    entry_session: date
    signal_session: date
    exit_session: date
    side: Side
    sector: str
    reason: str
    signal_strength: float
    costs: float = 0
    mae: float = 0
    mfe: float = 0
    entry_spread_bps: float = 0
    entry_slippage: float = 0


@dataclass
class ScheduledOrder:
    symbol: str
    side: Side
    qty: float
    session: date
    signal_session: date
    reason: str
    signal_strength: float
    sector: str
    hold: int
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    opening: bool = True
    reference_notional: float = 0


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    trades: pd.DataFrame
    costs: float
    slippage: float
    blocked: int
    model: str


@dataclass
class _Book:
    cash: float
    positions: dict[str, OpenPosition] = field(default_factory=dict)
    pending: list[ScheduledOrder] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    equity_rows: list[tuple[date, float]] = field(default_factory=list)
    costs: float = 0
    slippage: float = 0
    blocked: int = 0


def _spread_price(bar: dict) -> float:
    if bar.get("bid") and bar.get("ask"):
        return max(float(bar["ask"]) - float(bar["bid"]), 0)
    bps = float(bar.get("spread_bps") or 10)
    return float(bar["close"]) * bps / 10_000


def execution_price(side: Side, bar: dict, qty: float, model: ExecutionModelName) -> dict | None:
    """Fill quote. Spread and slippage are inside price. Commission is extra cash."""
    open_px = float(bar["open"])
    close_px = float(bar["close"])
    dollar = max(float(bar.get("dollar_volume") or 0), 1.0)
    notional = abs(qty) * open_px
    participation = notional / dollar
    spread = _spread_price(bar)
    direction = 1 if side == Side.BUY else -1
    if model == ExecutionModelName.OPTIMISTIC:
        slip_px = open_px * 0.0001
        return {
            "price": open_px + direction * slip_px,
            "spread_dollars": slip_px * abs(qty),
            "slippage_dollars": 0.0,
            "commission": 0.0,
            "filled_qty": abs(qty),
        }
    if model == ExecutionModelName.EXPECTED:
        slip_px = open_px * min(0.002, 0.10 * participation)
        commission = 0.000166 * abs(qty) if side == Side.SELL else 0.0
        return {
            "price": open_px + direction * (spread / 2 + slip_px),
            "spread_dollars": (spread / 2) * abs(qty),
            "slippage_dollars": slip_px * abs(qty),
            "commission": commission,
            "filled_qty": abs(qty),
        }
    filled = abs(qty)
    if participation > 0.20:
        return None
    if participation > 0.05:
        filled *= 0.5
    slip_px = open_px * (0.0005 + 0.25 * participation)
    anchor = max(open_px, close_px) if side == Side.BUY else min(open_px, close_px)
    return {
        "price": anchor + direction * (spread + slip_px),
        "spread_dollars": spread * filled,
        "slippage_dollars": slip_px * filled,
        "commission": 0.005 * filled,
        "filled_qty": filled,
    }


def run_backtest(
    bars: dict[tuple[date, str], dict],
    features: dict[tuple[date, str], dict],
    dates: list[date],
    strategy: ReversalStrategy,
    model: ExecutionModelName,
    *,
    starting_cash: float = 100_000,
    states: dict[date, object] | None = None,
    splits: dict[tuple[date, str], float] | None = None,
    dividends: dict[tuple[date, str], float] | None = None,
    apply_regime_scalar: bool = False,
    limits: RiskLimits | None = None,
) -> BacktestResult:
    book = _Book(cash=starting_cash)
    risk_limits = limits or RiskLimits()
    symbols = sorted({symbol for _, symbol in bars})
    for index, day in enumerate(dates):
        _apply_corporate_actions(book, day, splits or {}, dividends or {})
        todays = [order for order in book.pending if order.session == day]
        book.pending = [order for order in book.pending if order.session != day]
        for order in todays:
            bar = bars.get((day, order.symbol))
            if bar is None:
                book.blocked += 1
                continue
            if order.signal_session >= day:
                book.blocked += 1
                continue
            filled = _fill_order(book, order, bar, model)
            if filled is None:
                book.blocked += 1
        _mark(book, day, bars, symbols)
        cross = [features[(day, symbol)] for symbol in symbols if (day, symbol) in features]
        state = states.get(day) if states else None
        targets = strategy.targets(day, cross, state, apply_regime_scalar=apply_regime_scalar)
        held = set(book.positions)
        for target in targets:
            if target.symbol in held:
                continue
            nxt = next_session(day)
            if nxt not in dates and index == len(dates) - 1:
                continue
            bar = bars.get((day, target.symbol))
            if bar is None:
                book.blocked += 1
                continue
            price = float(bar["close"])
            qty = target.target_notional / price if price else 0
            if qty <= 0:
                continue
            intent = OrderIntent(
                client_order_id=f"bt_{uuid4().hex}",
                symbol=target.symbol,
                side=target.side,
                qty=qty,
                signal_ts=datetime(day.year, day.month, day.day, 16, 0, tzinfo=timezone.utc),
                decision_session=day,
                scheduled_session=nxt,
                strategy=STRATEGY_NAME,
                strategy_version=STRATEGY_VERSION,
                reason_code=target.reason_code,
                signal_strength=target.signal_strength,
                expected_spread_bps=float(bar.get("spread_bps") or 0),
                sector=target.sector,
                correlation_id="backtest",
                reference_price=price,
            )
            decision = evaluate_order(
                intent,
                risk_limits,
                _risk_snapshot(book, bar, risk_limits, pending=book.pending),
            )
            if not decision.approved:
                book.blocked += 1
                continue
            book.pending.append(
                ScheduledOrder(
                    symbol=target.symbol,
                    side=target.side,
                    qty=decision.approved_qty,
                    session=nxt,
                    signal_session=day,
                    reason=target.reason_code,
                    signal_strength=target.signal_strength,
                    sector=target.sector,
                    hold=target.hold_sessions,
                    reference_notional=decision.approved_qty * price,
                )
            )
    equity = pd.Series(
        [value for _, value in book.equity_rows],
        index=pd.to_datetime([day for day, _ in book.equity_rows]),
    )
    returns = equity.pct_change().fillna(0)
    trades = pd.DataFrame(book.trades)
    return BacktestResult(
        equity=equity,
        returns=returns,
        trades=trades,
        costs=book.costs,
        slippage=book.slippage,
        blocked=book.blocked,
        model=model.value,
    )


def _fill_order(book: _Book, order: ScheduledOrder, bar: dict, model: ExecutionModelName):
    if order.order_type == OrderType.LIMIT and order.limit_price is not None:
        if order.side == Side.BUY and float(bar["low"]) > order.limit_price:
            return None
        if order.side == Side.SELL and float(bar["high"]) < order.limit_price:
            return None
    if order.order_type == OrderType.STOP and order.stop_price is not None:
        if order.side == Side.SELL and float(bar["low"]) > order.stop_price:
            return None
    quote = execution_price(order.side, bar, order.qty, model)
    if quote is None:
        return None
    price = float(quote["price"])
    filled_qty = float(quote["filled_qty"])
    commission = float(quote["commission"])
    spread_cost = float(quote["spread_dollars"])
    slip_cost = float(quote["slippage_dollars"])
    if order.order_type == OrderType.LIMIT and order.limit_price is not None and model == ExecutionModelName.STRESS:
        if order.side == Side.BUY:
            price = max(price, order.limit_price)
        else:
            price = min(price, order.limit_price)
    book.costs += spread_cost + slip_cost + commission
    book.slippage += slip_cost
    book.cash -= commission
    if order.opening:
        signed = filled_qty if order.side == Side.BUY else -filled_qty
        book.cash -= signed * price
        exit_on = next_session(order.session, order.hold)
        book.positions[order.symbol] = OpenPosition(
            symbol=order.symbol,
            qty=signed,
            entry_price=price,
            entry_session=order.session,
            signal_session=order.signal_session,
            exit_session=exit_on,
            side=order.side,
            sector=order.sector,
            reason=order.reason,
            signal_strength=order.signal_strength,
            costs=spread_cost + slip_cost + commission,
            entry_spread_bps=float(bar.get("spread_bps") or 0),
            entry_slippage=slip_cost,
        )
        book.pending.append(
            ScheduledOrder(
                symbol=order.symbol,
                side=Side.SELL if order.side == Side.BUY else Side.BUY,
                qty=filled_qty,
                session=exit_on,
                signal_session=order.session,
                reason="scheduled_exit",
                signal_strength=order.signal_strength,
                sector=order.sector,
                hold=order.hold,
                opening=False,
            )
        )
        return price
    position = book.positions.get(order.symbol)
    if position is None:
        return None
    close_qty = min(abs(position.qty), filled_qty)
    direction = 1 if position.qty > 0 else -1
    exit_side = Side.SELL if direction > 0 else Side.BUY
    if order.side != exit_side:
        return None
    cash_delta = close_qty * price * direction
    # Long: sell, cash increases by price*qty. direction 1, cash_delta positive. book.cash += ?
    # We subtracted signed*price on entry. On exit, add back close_qty * price * direction for a long
    # (sell receives cash). For a short, direction -1, cash_delta negative (pay to cover). Correct.
    book.cash += close_qty * price * direction
    pnl = (price - position.entry_price) * close_qty * direction
    holding = (order.session - position.entry_session).days
    book.trades.append(
        {
            "symbol": order.symbol,
            "side": position.side.value,
            "qty": close_qty,
            "entry_price": position.entry_price,
            "exit_price": price,
            "pnl": pnl,
            "signal_session": str(position.signal_session),
            "entry_session": str(position.entry_session),
            "exit_session": str(order.session),
            "holding_sessions": max(holding, 1),
            "reason": position.reason,
            "signal_strength": position.signal_strength,
            "mae": position.mae,
            "mfe": position.mfe,
            "costs": position.costs + spread_cost + slip_cost,
            "slippage": position.entry_slippage + slip_cost,
            "sector": position.sector,
        }
    )
    book.positions.pop(order.symbol, None)
    return price


def _risk_snapshot(book: _Book, bar: dict, limits: RiskLimits, pending: list[ScheduledOrder] | None = None) -> RiskSnapshot:
    equity = book.equity_rows[-1][1] if book.equity_rows else book.cash
    positions = [
        PositionView(
            symbol=symbol,
            qty=position.qty,
            avg_price=position.entry_price,
            sector=position.sector,
            market_price=position.entry_price,
            notional=position.qty * position.entry_price,
        )
        for symbol, position in book.positions.items()
    ]
    for order in pending or []:
        if not order.opening or order.reference_notional == 0:
            continue
        signed = order.reference_notional if order.side == Side.BUY else -order.reference_notional
        positions.append(
            PositionView(
                symbol=order.symbol,
                qty=signed,
                avg_price=1,
                sector=order.sector,
                market_price=1,
                notional=signed,
            )
        )
    gross = sum(abs(item.notional) for item in positions)
    net = sum(item.notional for item in positions)
    account = AccountView(
        equity=equity,
        cash=book.cash,
        buying_power=max(book.cash, 0),
        gross_exposure=gross,
        net_exposure=net,
        peak_equity=max(equity, limits.account_equity_reference),
    )
    return RiskSnapshot(
        account=account,
        positions=positions,
        price=float(bar["close"]),
        dollar_volume=float(bar.get("dollar_volume") or 0),
        spread_bps=float(bar.get("spread_bps") or 0),
        estimated_slippage_bps=5,
        broker_connected=True,
        reconciliation_ok=True,
        data_trustworthy=True,
    )


def _mark(book: _Book, day: date, bars: dict, symbols: list[str]) -> None:
    market_value = 0.0
    for symbol, position in list(book.positions.items()):
        bar = bars.get((day, symbol))
        if bar is None:
            market_value += position.qty * position.entry_price
            continue
        price = float(bar["close"])
        excursion = (price - position.entry_price) * (1 if position.qty > 0 else -1)
        position.mfe = max(position.mfe, excursion)
        position.mae = min(position.mae, excursion)
        market_value += position.qty * price
        if position.qty < 0:
            borrow = abs(position.qty * price) * 0.0001
            book.cash -= borrow
            book.costs += borrow
    book.equity_rows.append((day, book.cash + market_value))


def _apply_corporate_actions(book, day, splits, dividends) -> None:
    for symbol, position in list(book.positions.items()):
        ratio = splits.get((day, symbol))
        if ratio:
            qty, price = apply_position_split(position.qty, position.entry_price, ratio)
            position.qty = qty
            position.entry_price = price
        amount = dividends.get((day, symbol))
        if amount and position.qty > 0:
            book.cash += cash_dividend(position.qty, amount)
