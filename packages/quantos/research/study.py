"""Pre-registered reversal study. Synthetic output is not a market conclusion."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd

from quantos.backtest.engine import run_backtest
from quantos.contracts.models import ExecutionModelName
from quantos.features.reversal import reversal_features
from quantos.research.metrics import monte_carlo_max_drawdown, performance_report
from quantos.research.sealed import SealedWindow
from quantos.research.synthetic import synthetic_panel
from quantos.risk.engine import RiskLimits
from quantos.strategy.reversal import STRATEGY_VERSION, ReversalStrategy

# Size, spread, and liquidity gates stay on. The live loss halt is not applied
# inside the historical measurement, because it would censor the sample after
# the first drawdown. The order pipeline still uses config/risk_limits.yml.
RESEARCH_LIMITS = RiskLimits(
    max_drawdown_fraction=1.0,
    max_daily_loss=1_000_000_000,
    max_weekly_loss=1_000_000_000,
    max_open_positions=80,
    max_gross_exposure=500_000,
    max_net_exposure=250_000,
    max_orders_per_day=400,
    max_daily_turnover=5_000_000,
    max_sector_notional=250_000,
    max_concentration=1.0,
    max_leverage=3.0,
)

GRID = ((1, 1), (1, 5), (5, 1), (5, 5))
N_TRIALS = len(GRID)


def _revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "uncommitted"


def _panel_maps(frame: pd.DataFrame, lookback: int) -> tuple[dict, dict, list[date]]:
    featured = reversal_features(frame, lookback)
    bars: dict[tuple[date, str], dict] = {}
    features: dict[tuple[date, str], dict] = {}
    for row in frame.to_dict(orient="records"):
        day = row["session_date"]
        if not isinstance(day, date):
            day = pd.to_datetime(day).date()
            row["session_date"] = day
        bars[(day, row["symbol"])] = row
    for row in featured.to_dict(orient="records"):
        day = row["session_date"]
        if not isinstance(day, date):
            day = pd.to_datetime(day).date()
            row["session_date"] = day
        features[(day, row["symbol"])] = row
    dates = sorted({day for day, _ in bars})
    return bars, features, dates


def _slice_metrics(result, start: date, n_trials: int) -> dict:
    equity = result.equity[result.equity.index.date >= start]
    returns = equity.pct_change().fillna(0)
    trades = result.trades
    if not trades.empty:
        trades = trades[pd.to_datetime(trades["entry_session"]).dt.date >= start]
    bench = returns * 0
    return performance_report(
        equity,
        returns,
        trades,
        bench,
        n_trials=n_trials,
        costs=result.costs,
        slippage=result.slippage,
    )


def run_reversal_study(
    root: Path,
    *,
    n_liquid: int = 24,
    n_illiquid: int = 6,
    seed: int = 7,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    sealed = SealedWindow.from_file(root / "config" / "sealed_window.yml")
    frame = synthetic_panel(
        n_liquid=n_liquid,
        n_illiquid=n_illiquid,
        seed=seed,
        **{key: value for key, value in {"start": start, "end": end}.items() if value is not None},
    )
    dates = sorted(pd.to_datetime(frame["session_date"]).dt.date.unique())
    sealed.assert_research_dates(list(dates), "research")
    split_at = dates[int(len(dates) * 0.6)]
    experiments = []
    stress_scores: dict[tuple[int, int], float] = {}
    for lookback, hold in GRID:
        bars, features, _ = _panel_maps(frame, lookback)
        for model in ExecutionModelName:
            strategy = ReversalStrategy(lookback, hold)
            result = run_backtest(
                bars,
                features,
                dates,
                strategy,
                model,
                limits=RESEARCH_LIMITS,
                apply_regime_scalar=False,
            )
            metrics = _slice_metrics(result, split_at, N_TRIALS)
            record = {
                "experiment_id": f"reversal-lb{lookback}-h{hold}-{model.value}",
                "git_revision": _revision(),
                "data_version": f"synthetic-seed-{seed}-liquid-{n_liquid}-illiquid-{n_illiquid}",
                "feature_set": f"residual_lookback_{lookback}",
                "parameters": {"lookback": lookback, "hold": hold, "decile": 0.1},
                "train_window": f"{dates[0]}:{split_at}",
                "validation_window": f"{split_at}:{dates[-1]}",
                "test_window": "sealed-not-opened",
                "cost_assumptions": {
                    "model": model.value,
                    "live_loss_halt_applied": False,
                    "reason": "Live loss, leverage, and concentration halts would censor the sample after the first drawdown. Per-trade notional, spread, and liquidity gates remain.",
                },
                "metrics": metrics,
                "n_trials": N_TRIALS,
                "notes": "Synthetic methodology run. Not evidence about US equities.",
                "monte_carlo": monte_carlo_max_drawdown(result.trades, paths=50),
            }
            if model == ExecutionModelName.STRESS:
                stress_scores[(lookback, hold)] = float(metrics["sharpe"])
                record["result"] = "recorded"
            else:
                record["result"] = "diagnostic"
            experiments.append(record)
    best_key = max(stress_scores, key=stress_scores.get)
    best = stress_scores[best_key]
    neighbor_scores = [
        score
        for key, score in stress_scores.items()
        if key != best_key and (key[0] == best_key[0] or key[1] == best_key[1])
    ]
    plateau = best > 0 and any(score > 0 and score >= 0.5 * best for score in neighbor_scores)
    reasons = [
        "market data was not used; the panel is synthetic",
        "survivorship-complete universe is unavailable",
        "sealed holdout was not opened",
        "skeptic veto: a synthetic plant cannot be promoted",
    ]
    if best <= 0:
        reasons.append("stress-model validation Sharpe is not positive")
    if best > 0 and not plateau:
        reasons.append("no stable parameter plateau under the stress model")
    summary = {
        "strategy": "liquid-short-horizon-reversal",
        "strategy_version": STRATEGY_VERSION,
        "state": "REJECTED",
        "hypothesis_status": "untested_on_market_data",
        "promotion": "rejected",
        "rejection_reasons": reasons,
        "n_trials": N_TRIALS,
        "stress_sharpe_by_parameter": {f"{a}:{b}": score for (a, b), score in stress_scores.items()},
        "best_stress_parameter": {"lookback": best_key[0], "hold": best_key[1], "sharpe": best},
        "parameter_plateau": plateau,
        "experiments": experiments,
        "real_market_evidence": False,
    }
    out = root / "research" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "reversal_study.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    sample = frame[frame["symbol"] == "L00"].tail(120)
    bars = [
        {
            "time": str(row.session_date),
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in sample.itertuples(index=False)
    ]
    (out / "chart_fixture.json").write_text(
        json.dumps({"symbol": "L00", "source": "synthetic", "bars": bars}),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    summary = run_reversal_study(Path.cwd())
    print(json.dumps({k: summary[k] for k in ("state", "hypothesis_status", "best_stress_parameter", "rejection_reasons")}, indent=2))


if __name__ == "__main__":
    main()
