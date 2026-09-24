"""Operational store. Experiments cannot be deleted."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class ExperimentImmutable(RuntimeError):
    pass


class OrderRow(Base):
    __tablename__ = "orders"
    client_order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(40))
    strategy: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrderEventRow(Base):
    __tablename__ = "order_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_order_id: Mapped[str] = mapped_column(String(64))
    from_state: Mapped[str] = mapped_column(String(40))
    to_state: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PositionRow(Base):
    __tablename__ = "positions"
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    qty: Mapped[float] = mapped_column(Float)
    avg_price: Mapped[float] = mapped_column(Float)
    sector: Mapped[str] = mapped_column(String(64), default="UNKNOWN")


class AccountRow(Base):
    __tablename__ = "account"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash: Mapped[float] = mapped_column(Float)
    equity: Mapped[float] = mapped_column(Float)
    peak_equity: Mapped[float] = mapped_column(Float)
    day_pnl: Mapped[float] = mapped_column(Float, default=0)
    week_pnl: Mapped[float] = mapped_column(Float, default=0)


class ExperimentRow(Base):
    __tablename__ = "experiments"
    experiment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    git_revision: Mapped[str] = mapped_column(String(64))
    data_version: Mapped[str] = mapped_column(String(128))
    feature_set: Mapped[str] = mapped_column(String(128))
    parameters: Mapped[str] = mapped_column(Text)
    train_window: Mapped[str] = mapped_column(String(64))
    validation_window: Mapped[str] = mapped_column(String(64))
    test_window: Mapped[str] = mapped_column(String(64))
    cost_assumptions: Mapped[str] = mapped_column(Text)
    metrics: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str] = mapped_column(Text)
    n_trials: Mapped[int] = mapped_column(Integer)


class FillRow(Base):
    __tablename__ = "fills"
    fill_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32))
    qty: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    payload: Mapped[str] = mapped_column(Text)


class AuditRow(Base):
    __tablename__ = "trade_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_order_id: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)


class ShadowRow(Base):
    __tablename__ = "shadow_orders"
    client_order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class OpsStore:
    def __init__(self, url: str) -> None:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args, future=True)

    def migrate(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return Session(self.engine)

    def ping(self) -> float:
        import time

        started = time.perf_counter()
        with self.engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return (time.perf_counter() - started) * 1000

    def save_order(self, client_order_id: str, payload: dict[str, Any], state: str) -> None:
        now = datetime.now(timezone.utc)
        with self.session() as session:
            existing = session.get(OrderRow, client_order_id)
            if existing is None:
                session.add(
                    OrderRow(
                        client_order_id=client_order_id,
                        symbol=payload["symbol"],
                        side=payload["side"],
                        qty=float(payload["qty"]),
                        state=state,
                        strategy=payload.get("strategy", ""),
                        correlation_id=payload.get("correlation_id", ""),
                        payload=json.dumps(payload),
                        updated_at=now,
                    )
                )
                session.add(
                    OrderEventRow(
                        client_order_id=client_order_id,
                        from_state="",
                        to_state=state,
                        detail="created",
                        at=now,
                    )
                )
            session.commit()

    def transition(self, client_order_id: str, to_state: str, detail: str = "") -> None:
        now = datetime.now(timezone.utc)
        with self.session() as session:
            row = session.get(OrderRow, client_order_id)
            if row is None:
                raise KeyError(client_order_id)
            previous = row.state
            row.state = to_state
            row.updated_at = now
            session.add(
                OrderEventRow(
                    client_order_id=client_order_id,
                    from_state=previous,
                    to_state=to_state,
                    detail=detail,
                    at=now,
                )
            )
            session.commit()

    def get_order(self, client_order_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.get(OrderRow, client_order_id)
            if row is None:
                return None
            return {"state": row.state, **json.loads(row.payload)}

    def list_orders(self) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.scalars(select(OrderRow).order_by(OrderRow.updated_at.desc())).all()
            return [{"state": row.state, **json.loads(row.payload)} for row in rows]

    def known_order_ids(self) -> set[str]:
        with self.session() as session:
            return set(session.scalars(select(OrderRow.client_order_id)).all())

    def record_fill(self, fill_id: str, payload: dict[str, Any]) -> bool:
        """Return False when the fill id was already stored."""
        with self.session() as session:
            if session.get(FillRow, fill_id) is not None:
                return False
            session.add(
                FillRow(
                    fill_id=fill_id,
                    client_order_id=payload["client_order_id"],
                    symbol=payload["symbol"],
                    qty=float(payload["qty"]),
                    price=float(payload["price"]),
                    payload=json.dumps(payload),
                )
            )
            session.commit()
            return True

    def add_experiment(self, record: dict[str, Any]) -> None:
        with self.session() as session:
            if session.get(ExperimentRow, record["experiment_id"]) is not None:
                return
            session.add(
                ExperimentRow(
                    experiment_id=record["experiment_id"],
                    created_at=datetime.now(timezone.utc),
                    git_revision=record.get("git_revision", "uncommitted"),
                    data_version=record.get("data_version", ""),
                    feature_set=record.get("feature_set", ""),
                    parameters=json.dumps(record.get("parameters", {})),
                    train_window=record.get("train_window", ""),
                    validation_window=record.get("validation_window", ""),
                    test_window=record.get("test_window", "sealed-not-used"),
                    cost_assumptions=json.dumps(record.get("cost_assumptions", {})),
                    metrics=json.dumps(record.get("metrics", {})),
                    result=record.get("result", "inconclusive"),
                    notes=record.get("notes", ""),
                    n_trials=int(record.get("n_trials", 1)),
                )
            )
            session.commit()

    def list_experiments(self) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.scalars(select(ExperimentRow)).all()
            result = []
            for row in rows:
                result.append(
                    {
                        "experiment_id": row.experiment_id,
                        "git_revision": row.git_revision,
                        "data_version": row.data_version,
                        "feature_set": row.feature_set,
                        "parameters": json.loads(row.parameters),
                        "train_window": row.train_window,
                        "validation_window": row.validation_window,
                        "test_window": row.test_window,
                        "cost_assumptions": json.loads(row.cost_assumptions),
                        "metrics": json.loads(row.metrics),
                        "result": row.result,
                        "notes": row.notes,
                        "n_trials": row.n_trials,
                    }
                )
            return result

    def delete_experiment(self, experiment_id: str) -> None:
        raise ExperimentImmutable(f"Experiments cannot be deleted ({experiment_id})")

    def save_shadow(self, client_order_id: str, payload: dict[str, Any]) -> None:
        with self.session() as session:
            if session.get(ShadowRow, client_order_id) is None:
                session.add(ShadowRow(client_order_id=client_order_id, payload=json.dumps(payload)))
                session.commit()

    def list_shadow(self) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.scalars(select(ShadowRow)).all()
            return [json.loads(row.payload) for row in rows]

    def save_audit(self, client_order_id: str, payload: dict[str, Any]) -> None:
        with self.session() as session:
            session.add(AuditRow(client_order_id=client_order_id, payload=json.dumps(payload)))
            session.commit()

    def upsert_position(self, symbol: str, qty: float, avg_price: float, sector: str) -> None:
        with self.session() as session:
            row = session.get(PositionRow, symbol)
            if row is None:
                session.add(PositionRow(symbol=symbol, qty=qty, avg_price=avg_price, sector=sector))
            else:
                row.qty = qty
                row.avg_price = avg_price
                row.sector = sector
            session.commit()

    def list_positions(self) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.scalars(select(PositionRow)).all()
            return [
                {"symbol": row.symbol, "qty": row.qty, "avg_price": row.avg_price, "sector": row.sector}
                for row in rows
            ]

    def ensure_account(self, cash: float) -> None:
        with self.session() as session:
            row = session.get(AccountRow, 1)
            if row is None:
                session.add(AccountRow(id=1, cash=cash, equity=cash, peak_equity=cash, day_pnl=0, week_pnl=0))
                session.commit()

    def account(self) -> dict[str, float]:
        with self.session() as session:
            row = session.get(AccountRow, 1)
            if row is None:
                return {"cash": 0, "equity": 0, "peak_equity": 0, "day_pnl": 0, "week_pnl": 0}
            return {
                "cash": row.cash,
                "equity": row.equity,
                "peak_equity": row.peak_equity,
                "day_pnl": row.day_pnl,
                "week_pnl": row.week_pnl,
            }

    def update_account(self, **values: float) -> None:
        with self.session() as session:
            row = session.get(AccountRow, 1)
            if row is None:
                row = AccountRow(id=1, cash=0, equity=0, peak_equity=0, day_pnl=0, week_pnl=0)
                session.add(row)
                session.flush()
            for key, value in values.items():
                setattr(row, key, value)
            session.commit()
