"""Shared contracts. Other layers depend on this package, not on each other."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TradingMode(str, Enum):
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


class StrategyState(str, Enum):
    IDEA = "IDEA"
    RESEARCHING = "RESEARCHING"
    REJECTED = "REJECTED"
    BACKTESTED = "BACKTESTED"
    VALIDATED = "VALIDATED"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    LIMITED_LIVE = "LIMITED_LIVE"
    PRODUCTION = "PRODUCTION"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


LIVE_STATES = {StrategyState.LIMITED_LIVE, StrategyState.PRODUCTION}


class OrderState(str, Enum):
    CREATED = "CREATED"
    RISK_APPROVED = "RISK_APPROVED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


TERMINAL_ORDER_STATES = {
    OrderState.FILLED,
    OrderState.CANCELLED,
    OrderState.REJECTED,
    OrderState.EXPIRED,
}

ALLOWED_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.CREATED: {OrderState.RISK_APPROVED, OrderState.REJECTED},
    OrderState.RISK_APPROVED: {OrderState.SUBMITTED, OrderState.REJECTED, OrderState.CANCELLED},
    OrderState.SUBMITTED: {
        OrderState.ACKNOWLEDGED,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.REJECTED,
        OrderState.CANCEL_PENDING,
        OrderState.RECONCILIATION_REQUIRED,
        OrderState.EXPIRED,
    },
    OrderState.ACKNOWLEDGED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.EXPIRED,
        OrderState.RECONCILIATION_REQUIRED,
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING,
        OrderState.CANCELLED,
        OrderState.RECONCILIATION_REQUIRED,
    },
    OrderState.CANCEL_PENDING: {OrderState.CANCELLED, OrderState.FILLED, OrderState.RECONCILIATION_REQUIRED},
    OrderState.RECONCILIATION_REQUIRED: {
        OrderState.ACKNOWLEDGED,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.EXPIRED,
    },
    OrderState.FILLED: set(),
    OrderState.CANCELLED: set(),
    OrderState.REJECTED: set(),
    OrderState.EXPIRED: set(),
}


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class ExecutionModelName(str, Enum):
    OPTIMISTIC = "optimistic"
    EXPECTED = "expected"
    STRESS = "stress"


class KillReason(str, Enum):
    MANUAL = "manual"
    RISK = "risk"
    MARKET_DATA = "market_data"
    BROKER = "broker"
    STRATEGY_ANOMALY = "strategy_anomaly"
    MODEL_DRIFT = "model_drift"
    LOSS_LIMIT = "loss_limit"
    UNEXPECTED_POSITION = "unexpected_position"
    RECONCILIATION = "reconciliation"


class KillAction(str, Enum):
    STOP_NEW = "stop_new"
    CANCEL_OPEN = "cancel_open"
    REDUCE_ONLY = "reduce_only"


class ClaimKind(str, Enum):
    FACT = "fact"
    HYPOTHESIS = "hypothesis"
    CORRELATION = "correlation"
    STATISTICAL_EVIDENCE = "statistical_evidence"
    SPECULATION = "speculation"


class Bar(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    session_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    dollar_volume: float
    bid: float | None = None
    ask: float | None = None
    spread_bps: float | None = None
    sector: str = "UNKNOWN"
    source: str
    adjustment: Literal["raw", "split", "total_return"] = "raw"
    exchange_ts: datetime | None = None
    ingest_ts: datetime | None = None
    liquid: bool = True


class Quote(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    bid: float
    ask: float
    bid_size: float = 0
    ask_size: float = 0
    exchange_ts: datetime | None = None
    receive_ts: datetime | None = None
    source: str = "unknown"


class TargetWeight(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    target_notional: float
    side: Side
    reason_code: str
    signal_strength: float
    hold_sessions: int
    sector: str = "UNKNOWN"


class OrderIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str
    symbol: str
    side: Side
    qty: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    signal_ts: datetime
    decision_session: date
    scheduled_session: date
    strategy: str
    strategy_version: str
    reason_code: str
    signal_strength: float = 0
    expected_spread_bps: float = 0
    expected_slippage_bps: float = 0
    expected_holding_sessions: int = 1
    sector: str = "UNKNOWN"
    correlation_id: str
    reduce_only: bool = False
    reference_price: float = 0


class RiskDecision(BaseModel):
    approved: bool
    approved_qty: float
    reasons: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)


class PositionView(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    sector: str = "UNKNOWN"
    market_price: float = 0
    notional: float = 0


class AccountView(BaseModel):
    equity: float
    cash: float
    buying_power: float
    day_pnl: float = 0
    week_pnl: float = 0
    total_pnl: float = 0
    drawdown: float = 0
    gross_exposure: float = 0
    net_exposure: float = 0
    peak_equity: float = 0


class MarketStateView(BaseModel):
    asof: date
    realized_vol: float
    trend: float
    dispersion: float
    breadth: float
    median_spread_bps: float
    median_dollar_volume: float
    regime: str
    exposure_scalar: float


class Claim(BaseModel):
    agent: str
    kind: ClaimKind
    statement: str
    refs: list[str] = Field(default_factory=list)


class SkepticVerdict(BaseModel):
    veto: bool
    objections: list[Claim]
