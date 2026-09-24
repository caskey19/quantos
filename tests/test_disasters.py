"""Failure cases the platform has to survive without sending a second order or ignoring a bad price."""

from datetime import date, datetime, timezone

from quantos.contracts.models import AccountView, KillReason, Side
from quantos.risk.engine import RiskLimits, RiskSnapshot, evaluate_order
from quantos.risk.killswitch import KillSwitch
from tests.test_core import _intent, _snap


def test_price_outlier_is_blocked():
    decision = evaluate_order(_intent(), RiskLimits(), _snap(last_return=0.8))
    assert decision.approved is False
    assert "abnormal_volatility" in decision.checks


def test_loss_limit_stops_new_risk():
    account = AccountView(equity=99_000, cash=99_000, buying_power=99_000, day_pnl=-600, peak_equity=100_000)
    decision = evaluate_order(_intent(), RiskLimits(), _snap(account=account))
    assert decision.approved is False


def test_strategy_anomaly_kill_stops_entries():
    kill = KillSwitch()
    kill.trip(KillReason.STRATEGY_ANOMALY, "absurd quantity pattern")
    assert kill.blocks(_intent(qty=1_000_000), 0)


def test_market_data_kill_is_distinct_from_a_broker_kill():
    kill = KillSwitch()
    kill.trip(KillReason.MARKET_DATA, "feed frozen")
    assert kill.reason == KillReason.MARKET_DATA
    kill.trip(KillReason.BROKER, "socket down")
    assert kill.history[-1]["reason"] == "broker"


def test_database_outage_prevents_submit(monkeypatch, tmp_path):
    from quantos.execution.pipeline import OrderPipeline
    from quantos.brokers.simulated import SimulatedBroker
    from quantos.persistence.store import OpsStore
    from quantos.settings import Settings

    settings = Settings(
        trading_mode="paper",
        database_url=f"sqlite:///{tmp_path / 'ops.sqlite'}",
        checklist_path=tmp_path / "missing.yml",
        risk_path=tmp_path / "missing-risk.yml",
        sealed_path=tmp_path / "missing-sealed.yml",
        repo_root=tmp_path,
    )
    store = OpsStore(settings.database_url)
    store.migrate()

    def boom(*_args, **_kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(store, "save_order", boom)
    broker = SimulatedBroker()
    pipeline = OrderPipeline(store, broker, RiskLimits(), KillSwitch(), settings)
    try:
        pipeline.submit(_intent(), _snap())
    except RuntimeError as exc:
        assert "database" in str(exc)
    assert broker.submit_calls == []


def test_clock_and_session_date_are_explicit():
    now = datetime(2024, 6, 3, 14, 0, tzinfo=timezone.utc)
    snap = _snap(now=now, session_date=date(2024, 6, 3), enforce_market_hours=True)
    decision = evaluate_order(_intent(), RiskLimits(), snap)
    assert "market_hours" in decision.checks
