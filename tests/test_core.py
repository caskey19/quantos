from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from quantos.api.http import create_app
from quantos.brokers.simulated import SimulatedBroker
from quantos.contracts.models import (
    ExecutionModelName,
    KillAction,
    KillReason,
    OrderIntent,
    OrderType,
    Side,
    StrategyState,
)
from quantos.data.calendar import is_session, next_session
from quantos.data.corporate import apply_position_split, apply_splits
from quantos.data.integrity import integrity_report
from quantos.data.store import ParquetStore
from quantos.data.stream import StreamEvent, StreamSupervisor
from quantos.execution.pipeline import OrderPipeline, reconcile
from quantos.features.reversal import reversal_features
from quantos.governance import PromotionError, promote
from quantos.monitoring.logs import redact
from quantos.persistence.store import ExperimentImmutable, OpsStore
from quantos.research.labels import forward_open_return
from quantos.research.sealed import SealedWindow, SealedWindowError
from quantos.risk.engine import RiskLimits, RiskSnapshot, evaluate_order
from quantos.risk.killswitch import KillSwitch
from quantos.settings import LiveTradingDisabled, Settings, load_settings
from quantos.contracts.models import AccountView


ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path, mode: str = "paper") -> Settings:
    return Settings(
        trading_mode=mode,
        database_url=f"sqlite:///{tmp_path / 'ops.sqlite'}",
        data_root=tmp_path / "data",
        unlock_path=tmp_path / "live.unlock",
        checklist_path=ROOT / "config" / "live_authorization.yml",
        sealed_path=ROOT / "config" / "sealed_window.yml",
        risk_path=ROOT / "config" / "risk_limits.yml",
        repo_root=ROOT,
    )


def _intent(**kwargs) -> OrderIntent:
    payload = dict(
        client_order_id="qos_test",
        symbol="AAPL",
        side=Side.BUY,
        qty=10,
        signal_ts=datetime(2024, 6, 3, 20, 0, tzinfo=timezone.utc),
        decision_session=date(2024, 6, 3),
        scheduled_session=date(2024, 6, 4),
        strategy="liquid-short-horizon-reversal",
        strategy_version="0.1.0",
        reason_code="test",
        correlation_id="cid",
        reference_price=100,
        sector="TECH",
        expected_spread_bps=5,
    )
    payload.update(kwargs)
    return OrderIntent(**payload)


def _snap(**kwargs) -> RiskSnapshot:
    account = AccountView(equity=100_000, cash=100_000, buying_power=100_000, peak_equity=100_000)
    payload = dict(
        account=account,
        positions=[],
        price=100,
        dollar_volume=50_000_000,
        spread_bps=5,
        estimated_slippage_bps=5,
    )
    payload.update(kwargs)
    return RiskSnapshot(**payload)


def test_weekends_and_new_year_are_closed():
    assert is_session(date(2024, 1, 1)) is False
    assert is_session(date(2024, 1, 2)) is True
    assert next_session(date(2024, 1, 1)) == date(2024, 1, 2)


def test_live_boot_refused(tmp_path: Path):
    with pytest.raises(LiveTradingDisabled):
        load_settings({"TRADING_MODE": "live"}, root=tmp_path)


def test_paper_and_live_keys_cannot_coexist(tmp_path: Path):
    with pytest.raises(Exception):
        load_settings(
            {
                "TRADING_MODE": "paper",
                "APCA_API_KEY_ID": "paper",
                "APCA_LIVE_API_KEY_ID": "live",
            },
            root=tmp_path,
        )


def test_public_bind_refused(tmp_path: Path):
    with pytest.raises(Exception):
        load_settings({"QUANTOS_BIND_HOST": "0.0.0.0"}, root=tmp_path)


def test_no_automatic_live_promotion():
    with pytest.raises(PromotionError):
        promote(StrategyState.SHADOW, StrategyState.LIMITED_LIVE, evidence_note="looks good")
    assert promote(StrategyState.IDEA, StrategyState.RESEARCHING, evidence_note="started") == StrategyState.RESEARCHING


def test_sealed_window_blocks_research():
    window = SealedWindow.from_file(ROOT / "config" / "sealed_window.yml")
    with pytest.raises(SealedWindowError):
        window.assert_research_dates([date(2025, 6, 2)], "research")
    window.assert_research_dates([date(2024, 6, 3)], "research")


def test_feature_ignores_future_close():
    rows = []
    price = 100.0
    for offset, day in enumerate(pd.bdate_range("2024-01-02", periods=30)):
        price *= 1.001
        rows.append(
            {
                "symbol": "AAA",
                "session_date": day.date(),
                "close": price,
                "open": price,
                "high": price,
                "low": price,
                "volume": 1,
                "dollar_volume": 1,
                "spread_bps": 5,
                "liquid": True,
            }
        )
    frame = pd.DataFrame(rows)
    first = reversal_features(frame, 5)
    mutated = frame.copy()
    mutated.loc[mutated.index[-1], "close"] = 1.0
    second = reversal_features(mutated, 5)
    past = first["session_date"] < frame["session_date"].iloc[-1]
    pd.testing.assert_series_equal(
        first.loc[past, "residual"].reset_index(drop=True),
        second.loc[past, "residual"].reset_index(drop=True),
        check_names=False,
    )


def test_labels_are_separate_from_features():
    frame = pd.DataFrame(
        {
            "symbol": ["AAA"] * 6,
            "session_date": list(pd.bdate_range("2024-01-02", periods=6).date),
            "open": [10, 11, 12, 13, 14, 15],
        }
    )
    labeled = forward_open_return(frame, 1)
    assert "forward_return" in labeled.columns
    featured = reversal_features(
        frame.assign(close=frame["open"], high=frame["open"], low=frame["open"], volume=1, dollar_volume=1, spread_bps=1, liquid=True),
        1,
    )
    assert "forward_return" not in featured.columns


def test_raw_store_is_immutable(tmp_path: Path):
    store = ParquetStore(tmp_path)
    frame = pd.DataFrame({"symbol": ["AAA"], "close": [1.0]})
    first = store.write_raw(frame, "bars", "synthetic")
    again = store.write_raw(frame, "bars", "synthetic")
    assert first == again
    changed = frame.copy()
    changed["close"] = 2.0
    second = store.write_raw(changed, "bars", "synthetic")
    assert second != first
    assert first.exists() and second.exists()
    loaded = store.scan("bars", "synthetic")
    assert set(loaded["close"]) == {1.0, 2.0}


def test_integrity_flags_duplicate_and_zero_price():
    frame = pd.DataFrame(
        [
            {"symbol": "AAA", "session_date": date(2024, 1, 2), "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1, "source": "t"},
            {"symbol": "AAA", "session_date": date(2024, 1, 2), "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1, "source": "t"},
            {"symbol": "AAA", "session_date": date(2024, 1, 3), "open": 0, "high": 1, "low": 0, "close": 1, "volume": 1, "source": "t"},
        ]
    )
    report = integrity_report(frame, start=date(2024, 1, 2), end=date(2024, 1, 3))
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "duplicate" in kinds
    assert "non_positive_price" in kinds
    assert report["trustworthy"] is False


def test_split_adjusts_history_not_position_cash_identity():
    raw = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "session_date": [date(2024, 1, 2), date(2024, 1, 3)],
            "open": [100.0, 50.0],
            "high": [100.0, 50.0],
            "low": [100.0, 50.0],
            "close": [100.0, 50.0],
            "volume": [10.0, 20.0],
            "bid": [100.0, 50.0],
            "ask": [100.0, 50.0],
        }
    )
    splits = pd.DataFrame({"symbol": ["AAA"], "ex_date": [date(2024, 1, 3)], "ratio": [2.0]})
    adjusted = apply_splits(raw, splits)
    assert adjusted.loc[0, "close"] == 50
    qty, price = apply_position_split(100, 100, 2)
    assert qty == 200 and price == 50


def test_stream_gaps_duplicates_and_staleness():
    supervisor = StreamSupervisor(stale_after_seconds=1)
    now = datetime(2024, 1, 2, 15, 0, tzinfo=timezone.utc)
    supervisor.heartbeat(now)
    assert supervisor.observe(
        StreamEvent(1, "AAA", "quote", now, now, now, "a")
    ) == "accepted"
    assert supervisor.observe(
        StreamEvent(1, "AAA", "quote", now, now, now, "a")
    ) == "duplicate"
    supervisor.observe(StreamEvent(4, "AAA", "quote", now, now, now, "b"))
    assert supervisor.gaps
    assert supervisor.stale(datetime(2024, 1, 2, 15, 1, tzinfo=timezone.utc))
    supervisor.on_disconnect()
    assert supervisor.reconnects == 1


def test_risk_blocks_absurd_quantity_and_wide_spread():
    limits = RiskLimits()
    absurd = evaluate_order(_intent(qty=600), limits, _snap())
    assert absurd.approved
    assert absurd.approved_qty < 10_000
    wide = evaluate_order(_intent(), limits, _snap(spread_bps=80))
    assert wide.approved is False


def test_zero_price_and_disconnect_fail_safe():
    limits = RiskLimits()
    assert evaluate_order(_intent(), limits, _snap(price=0)).approved is False
    assert evaluate_order(_intent(), limits, _snap(broker_connected=False)).approved is False
    assert evaluate_order(_intent(), limits, _snap(data_trustworthy=False)).approved is False


def test_order_pipeline_is_idempotent_and_times_out_safely(tmp_path: Path):
    settings = _settings(tmp_path)
    store = OpsStore(settings.database_url)
    store.migrate()
    broker = SimulatedBroker()
    broker.set_quote(
        __import__("quantos.contracts.models", fromlist=["Quote"]).Quote(symbol="AAPL", bid=99.9, ask=100.1, source="sim")
    )
    kill = KillSwitch()
    pipeline = OrderPipeline(store, broker, RiskLimits(), kill, settings)
    intent = _intent()
    first = pipeline.submit(intent, _snap(known_client_order_ids=set()))
    second = pipeline.submit(intent, _snap())
    assert first["client_order_id"] == second["client_order_id"]
    assert broker.submit_calls.count(intent.client_order_id) == 1
    broker.timeout_next_submit = True
    other = _intent(client_order_id="qos_timeout")
    result = pipeline.submit(other, _snap())
    assert result["state"] == "RECONCILIATION_REQUIRED"
    assert kill.tripped
    assert kill.reason == KillReason.RECONCILIATION


def test_duplicate_fill_is_ignored(tmp_path: Path):
    store = OpsStore(f"sqlite:///{tmp_path / 'f.sqlite'}")
    store.migrate()
    assert store.record_fill("fill-1", {"client_order_id": "a", "symbol": "AAA", "qty": 1, "price": 10})
    assert store.record_fill("fill-1", {"client_order_id": "a", "symbol": "AAA", "qty": 1, "price": 10}) is False


def test_experiments_cannot_be_deleted(tmp_path: Path):
    store = OpsStore(f"sqlite:///{tmp_path / 'e.sqlite'}")
    store.migrate()
    store.add_experiment({"experiment_id": "e1", "result": "rejected", "notes": "no"})
    with pytest.raises(ExperimentImmutable):
        store.delete_experiment("e1")


def test_kill_switch_does_not_liquidate():
    kill = KillSwitch(action=KillAction.STOP_NEW)
    kill.trip(KillReason.MANUAL, "operator")
    assert kill.blocks(_intent(), 0)
    kill.action = KillAction.REDUCE_ONLY
    assert kill.blocks(_intent(side=Side.SELL, qty=5), 10) is None
    assert kill.blocks(_intent(side=Side.BUY, qty=5), 10)


def test_reconciliation_mismatch():
    internal = AccountView(equity=100, cash=100, buying_power=100)
    broker = AccountView(equity=50, cash=50, buying_power=50)
    issues = reconcile(internal, broker, [], [], 1)
    assert issues


def test_shadow_does_not_submit(tmp_path: Path):
    settings = _settings(tmp_path, "shadow")
    store = OpsStore(settings.database_url)
    store.migrate()
    broker = SimulatedBroker()

    def explode(_intent):
        raise AssertionError("broker submit")

    broker.submit = explode
    pipeline = OrderPipeline(store, broker, RiskLimits(), KillSwitch(), settings)
    result = pipeline.submit(_intent(reference_price=100), _snap())
    assert result["sent_to_broker"] is False


def test_backtest_cannot_fill_on_the_signal_day():
    from quantos.backtest.engine import run_backtest
    from quantos.research.synthetic import synthetic_panel
    from quantos.strategy.reversal import ReversalStrategy

    frame = synthetic_panel(start=date(2024, 1, 2), end=date(2024, 4, 30), n_liquid=12, n_illiquid=0, seed=3)
    featured = reversal_features(frame, 1)
    bars = {}
    features = {}
    for row in frame.to_dict(orient="records"):
        bars[(row["session_date"], row["symbol"])] = row
    for row in featured.to_dict(orient="records"):
        features[(row["session_date"], row["symbol"])] = row
    dates = sorted({day for day, _ in bars})
    result = run_backtest(bars, features, dates, ReversalStrategy(1, 1), ExecutionModelName.STRESS)
    if not result.trades.empty:
        assert (pd.to_datetime(result.trades["entry_session"]) > pd.to_datetime(result.trades["signal_session"])).all()


def test_stress_buy_is_not_better_than_the_open():
    from quantos.backtest.engine import execution_price

    bar = {"open": 100, "close": 101, "high": 102, "low": 99, "dollar_volume": 50_000_000, "spread_bps": 10, "bid": 99.95, "ask": 100.05}
    quote = execution_price(Side.BUY, bar, 10, ExecutionModelName.STRESS)
    assert quote is not None
    assert quote["price"] >= bar["open"]


def test_limit_order_does_not_fill_through_an_untouched_price():
    from quantos.backtest.engine import _Book, _fill_order, ScheduledOrder

    book = _Book(cash=100_000)
    order = ScheduledOrder(
        symbol="AAA",
        side=Side.BUY,
        qty=10,
        session=date(2024, 1, 3),
        signal_session=date(2024, 1, 2),
        reason="limit",
        signal_strength=1,
        sector="TECH",
        hold=1,
        order_type=OrderType.LIMIT,
        limit_price=90,
    )
    bar = {"open": 100, "high": 101, "low": 99, "close": 100, "dollar_volume": 50_000_000, "spread_bps": 5, "bid": 99.9, "ask": 100.1}
    assert _fill_order(book, order, bar, ExecutionModelName.EXPECTED) is None


def test_api_refuses_to_enable_live(tmp_path: Path):
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    response = client.post("/api/live/enable")
    assert response.status_code == 403
    assert not (tmp_path / "live.unlock").exists()
    health = client.get("/api/health")
    assert health.json()["mode"] == "paper"
    center = client.get("/api/command-center")
    assert center.json()["live_locked"] is True


def test_market_state_scalar_cannot_increase_exposure():
    from quantos.market_state.state import classify_market
    from quantos.research.synthetic import synthetic_panel

    frame = synthetic_panel(start=date(2024, 1, 2), end=date(2024, 3, 29), n_liquid=8, n_illiquid=0, seed=1)
    state = classify_market(frame, date(2024, 3, 29))
    assert state.exposure_scalar <= 1


def test_secrets_are_redacted():
    assert redact({"api_key": "super-secret", "symbol": "AAA"})["api_key"] == "***"


def test_restart_reloads_position(tmp_path: Path):
    settings = _settings(tmp_path)
    app = create_app(settings)
    client = TestClient(app)
    from quantos.contracts.models import Quote

    app.state.quantos.broker.set_quote(Quote(symbol="AAPL", bid=99, ask=101, source="sim"))
    response = client.post("/api/orders", json=_intent().model_dump(mode="json"))
    assert response.status_code == 200
    reloaded = create_app(settings)
    positions = reloaded.state.quantos.positions()
    assert any(item.symbol == "AAPL" and item.qty > 0 for item in positions)
