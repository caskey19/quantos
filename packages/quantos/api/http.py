"""Local HTTP API. There is no route that creates a live unlock file."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from quantos.agents.session import session as research_session
from quantos.brokers.factory import build_broker
from quantos.brokers.simulated import SimulatedBroker
from quantos.contracts.models import AccountView, KillReason, OrderIntent, PositionView
from quantos.execution.pipeline import OrderPipeline, reconcile
from quantos.monitoring.logs import LatencyLog, log_event, new_correlation_id, process_health
from quantos.portfolio.book import exposures
from quantos.risk.engine import RiskLimits, RiskSnapshot
from quantos.risk.killswitch import KillSwitch
from quantos.settings import Settings, live_status, load_settings


class KillRequest(BaseModel):
    reason: str = "manual"
    detail: str = "operator"


class AppState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store_path = settings.database_url
        from quantos.persistence.store import OpsStore

        self.store = OpsStore(settings.database_url)
        self.store.migrate()
        self.store.ensure_account(100_000)
        self.broker = build_broker(settings)
        if isinstance(self.broker, SimulatedBroker):
            stored = self.store.account()
            if stored["equity"]:
                self.broker.cash = stored["cash"]
                self.broker.peak = stored["peak_equity"] or stored["equity"]
            for row in self.store.list_positions():
                self.broker._positions[row["symbol"]] = PositionView(
                    symbol=row["symbol"],
                    qty=row["qty"],
                    avg_price=row["avg_price"],
                    sector=row["sector"],
                    market_price=row["avg_price"],
                    notional=row["qty"] * row["avg_price"],
                )
        self.kill = KillSwitch()
        self.limits = RiskLimits.from_file(settings.risk_path) if settings.risk_path.exists() else RiskLimits()
        self.pipeline = OrderPipeline(self.store, self.broker, self.limits, self.kill, settings)
        self.latency = LatencyLog()
        self.study = _load_study(settings.repo_root)
        self.alerts: list[dict] = []

    def account_view(self) -> AccountView:
        return self.broker.account()

    def positions(self) -> list[PositionView]:
        stored = self.store.list_positions()
        if stored:
            return [
                PositionView(
                    symbol=row["symbol"],
                    qty=row["qty"],
                    avg_price=row["avg_price"],
                    sector=row["sector"],
                    market_price=row["avg_price"],
                    notional=row["qty"] * row["avg_price"],
                )
                for row in stored
            ]
        return self.broker.positions()


def _load_study(root: Path) -> dict:
    path = root / "research" / "results" / "reversal_study.json"
    if not path.exists():
        return {
            "state": "RESEARCHING",
            "hypothesis_status": "untested_on_market_data",
            "promotion": "not_run",
            "rejection_reasons": ["study artifact is not present yet"],
            "experiments": [],
            "real_market_evidence": False,
            "n_trials": 4,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings or load_settings()
    state = AppState(active)
    app = FastAPI(title="quant-os", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.state.quantos = state

    @app.get("/api/health")
    def health() -> dict:
        db_ms = state.store.ping()
        state.latency.observe("database_ms", db_ms)
        return {"ok": True, "mode": active.trading_mode, "database_ms": db_ms}

    @app.get("/api/session")
    def session_view() -> dict:
        status = live_status(active)
        return {
            "mode": active.trading_mode,
            "live_locked": not status["live_submission_allowed"],
            "live": status,
            "broker": state.broker.name,
            "paper_broker": getattr(state.broker, "paper", True),
        }

    @app.get("/api/checklist")
    def checklist() -> dict:
        return live_status(active)

    @app.post("/api/live/enable")
    def enable_live() -> None:
        log_event("live_enable_refused")
        raise HTTPException(status_code=403, detail="Live trading cannot be enabled through the API")

    @app.get("/api/command-center")
    def command_center() -> dict:
        account = state.account_view()
        positions = state.positions()
        exposure = exposures(positions)
        study = state.study
        return {
            "mode": active.trading_mode,
            "live_locked": True,
            "market_status": "paper-simulation" if active.trading_mode == "paper" else active.trading_mode,
            "account": account.model_dump(),
            "exposure": exposure,
            "positions": [item.model_dump() for item in positions],
            "strategy_state": study.get("state"),
            "hypothesis_status": study.get("hypothesis_status"),
            "regime": "unvalidated",
            "kill": state.kill.status(),
            "broker_connected": state.broker.connected(),
            "data_health": "synthetic" if not study.get("real_market_evidence") else "market",
            "research_status": study.get("promotion"),
            "blocked": state.pipeline.blocked[-8:],
            "recent_orders": state.store.list_orders()[:8],
        }

    @app.get("/api/orders")
    def orders() -> dict:
        return {"orders": state.store.list_orders(), "shadow": state.store.list_shadow()}

    @app.post("/api/orders")
    def submit_order(intent: OrderIntent) -> dict:
        correlation = new_correlation_id()
        log_event("order_intent", client_order_id=intent.client_order_id, correlation=correlation)
        account = state.account_view()
        snap = RiskSnapshot(
            account=account,
            positions=state.positions(),
            price=intent.reference_price or 1,
            dollar_volume=50_000_000,
            spread_bps=intent.expected_spread_bps or 5,
            estimated_slippage_bps=intent.expected_slippage_bps or 5,
            known_client_order_ids=state.store.known_order_ids(),
            broker_connected=state.broker.connected(),
            reconciliation_ok=not state.kill.tripped,
            data_trustworthy=True,
        )
        return state.pipeline.submit(intent, snap)

    @app.post("/api/kill")
    def kill(body: KillRequest) -> dict:
        try:
            reason = KillReason(body.reason)
        except ValueError:
            reason = KillReason.MANUAL
        state.kill.trip(reason, body.detail)
        state.alerts.append({"kind": "kill", "detail": body.detail})
        log_event("kill", reason=reason.value)
        return state.kill.status()

    @app.get("/api/strategy")
    def strategy() -> dict:
        return state.study

    @app.get("/api/research")
    def research() -> dict:
        return research_session(state.study)

    @app.get("/api/backtest")
    def backtest() -> dict:
        experiments = state.study.get("experiments") or []
        stress = [row for row in experiments if row.get("cost_assumptions", {}).get("model") == "stress"]
        return {
            "experiments": experiments,
            "stress": stress,
            "note": "Figures are synthetic until a market-data study is stored.",
            "real_market_evidence": state.study.get("real_market_evidence", False),
        }

    @app.get("/api/risk")
    def risk() -> dict:
        return {"limits": state.limits.model_dump(), "kill": state.kill.status(), "blocked": state.pipeline.blocked}

    @app.get("/api/performance")
    def performance() -> dict:
        return {
            "real_market_evidence": False,
            "best_stress_parameter": state.study.get("best_stress_parameter"),
            "stress_sharpe_by_parameter": state.study.get("stress_sharpe_by_parameter"),
            "rejection_reasons": state.study.get("rejection_reasons"),
        }

    @app.get("/api/scanner")
    def scanner() -> dict:
        return {
            "rows": [],
            "columns": ["symbol", "residual", "spread_bps", "dollar_volume", "regime", "excluded"],
            "note": "Scanner stays empty until market data for the reversal program is ingested.",
        }

    @app.get("/api/markets")
    def markets() -> dict:
        return {"feed": "none", "note": "No market session is connected. Paper broker is simulated unless Alpaca paper keys are present."}

    @app.get("/api/bars/{symbol}")
    def bars(symbol: str) -> dict:
        path = active.repo_root / "research" / "results" / "chart_fixture.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["requested"] = symbol
            payload["note"] = "Synthetic fixture. Not a market price."
            return payload
        return {"symbol": symbol, "bars": [], "source": "none"}

    @app.get("/api/data-health")
    def data_health() -> dict:
        return {
            "trustworthy": False,
            "reason": "No raw market dataset has been ingested. Synthetic research output is labeled synthetic.",
            "survivorship": "unresolved",
            "feed": "unconfigured",
        }

    @app.get("/api/system-health")
    def system_health() -> dict:
        db_ms = state.store.ping()
        return {
            "process": process_health(),
            "database_ms": db_ms,
            "latency": state.latency.snapshot(),
            "broker_connected": state.broker.connected(),
            "alerts": state.alerts,
            "kill": state.kill.status(),
        }

    @app.get("/api/positions")
    def positions() -> dict:
        rows = state.positions()
        return {"positions": [row.model_dump() for row in rows], "exposure": exposures(rows)}

    @app.post("/api/reconcile")
    def reconcile_now() -> dict:
        internal_positions = state.positions()
        broker_positions = state.broker.positions()
        internal_account = state.account_view()
        broker_account = state.broker.account()
        issues = reconcile(
            internal_account,
            broker_account,
            internal_positions,
            broker_positions,
            state.limits.reconciliation_tolerance,
        )
        if issues:
            state.kill.trip(KillReason.RECONCILIATION, "; ".join(issues))
            state.alerts.append({"kind": "reconciliation", "detail": issues})
        return {"ok": not issues, "issues": issues}

    return app


def main() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run(create_app(settings), host=settings.bind_host, port=settings.bind_port)
