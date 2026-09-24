"""Performance statistics. Raw return is one column among many."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _ann_factor(periods: int = 252) -> float:
    return math.sqrt(periods)


def max_drawdown(equity: pd.Series) -> tuple[float, float, int]:
    if equity.empty:
        return 0.0, 0.0, 0
    peak = equity.cummax()
    dd = equity / peak - 1
    worst = float(dd.min())
    average = float(dd.mean())
    duration = 0
    current = 0
    for value in dd:
        if value < 0:
            current += 1
            duration = max(duration, current)
        else:
            current = 0
    return worst, average, duration


def historical_var_es(returns: pd.Series, level: float = 0.05) -> tuple[float, float]:
    if returns.empty:
        return 0.0, 0.0
    cutoff = float(np.quantile(returns, level))
    tail = returns[returns <= cutoff]
    es = float(tail.mean()) if len(tail) else cutoff
    return cutoff, es


def bootstrap_sharpe_ci(
    returns: pd.Series,
    *,
    samples: int = 400,
    seed: int = 7,
    periods: int = 252,
) -> tuple[float, float]:
    if len(returns) < 5:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    values = returns.to_numpy()
    scores = []
    for _ in range(samples):
        draw = rng.choice(values, size=len(values), replace=True)
        std = draw.std(ddof=1)
        if std == 0:
            continue
        scores.append(draw.mean() / std * _ann_factor(periods))
    if not scores:
        return (float("nan"), float("nan"))
    return float(np.quantile(scores, 0.05)), float(np.quantile(scores, 0.95))


def deflated_sharpe_probability(
    sharpe: float,
    *,
    n_trials: int,
    n_obs: int,
    skew: float,
    kurtosis: float,
) -> float:
    """Probability the Sharpe exceeds the expected maximum of n_trials nulls.

    Bailey and López de Prado, The Deflated Sharpe Ratio (2014), simplified
    with a normal PSR. This is a penalty, not a proof of an edge.
    """
    from math import e as euler_e

    from scipy.stats import norm

    if n_obs < 3 or n_trials < 1:
        return 0.0
    sr = sharpe / math.sqrt(252) if abs(sharpe) > 2 else sharpe
    # The caller passes an annualized Sharpe. Convert to per-period.
    sr_period = sharpe / math.sqrt(252)
    var = (1 - skew * sr_period + ((kurtosis - 1) / 4) * sr_period**2) / (n_obs - 1)
    var = max(var, 1e-12)
    if n_trials == 1:
        sr0 = 0.0
    else:
        z1 = norm.ppf(1 - 1 / n_trials)
        z2 = norm.ppf(1 - 1 / (n_trials * euler_e))
        euler = 0.5772156649
        sr0 = math.sqrt(var) * ((1 - euler) * z1 + euler * z2)
    z = (sr_period - sr0) / math.sqrt(var)
    _ = sr
    return float(norm.cdf(z))


def trade_stats(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty or "pnl" not in trades.columns:
        return {
            "trades": 0,
            "hit_rate": 0,
            "profit_factor": 0,
            "expectancy": 0,
            "avg_winner": 0,
            "avg_loser": 0,
            "win_loss_ratio": 0,
            "avg_holding_sessions": 0,
            "median_holding_sessions": 0,
        }
    pnl = trades["pnl"].astype(float)
    winners = pnl[pnl > 0]
    losers = pnl[pnl < 0]
    gross_win = float(winners.sum())
    gross_loss = float(-losers.sum())
    holding = trades["holding_sessions"] if "holding_sessions" in trades.columns else pd.Series(dtype=float)
    return {
        "trades": float(len(pnl)),
        "hit_rate": float((pnl > 0).mean()),
        "profit_factor": gross_win / gross_loss if gross_loss else float("inf") if gross_win else 0.0,
        "expectancy": float(pnl.mean()),
        "avg_winner": float(winners.mean()) if len(winners) else 0.0,
        "avg_loser": float(losers.mean()) if len(losers) else 0.0,
        "win_loss_ratio": (
            abs(float(winners.mean()) / float(losers.mean())) if len(winners) and len(losers) and losers.mean() != 0 else 0.0
        ),
        "avg_holding_sessions": float(holding.mean()) if len(holding) else 0.0,
        "median_holding_sessions": float(holding.median()) if len(holding) else 0.0,
    }


def performance_report(
    equity: pd.Series,
    returns: pd.Series,
    trades: pd.DataFrame,
    benchmark: pd.Series | None = None,
    *,
    periods: int = 252,
    n_trials: int = 1,
    costs: float = 0,
    slippage: float = 0,
) -> dict[str, float | dict | None]:
    rets = returns.dropna()
    if rets.empty:
        ann_return = 0.0
        vol = 0.0
        sharpe = 0.0
        sortino = 0.0
    else:
        ann_return = float((1 + rets).prod() ** (periods / len(rets)) - 1)
        vol = float(rets.std(ddof=1) * _ann_factor(periods))
        sharpe = float(rets.mean() / rets.std(ddof=1) * _ann_factor(periods)) if rets.std(ddof=1) else 0.0
        downside = rets[rets < 0]
        down_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
        sortino = float(rets.mean() / down_std * _ann_factor(periods)) if down_std else 0.0
    worst, average_dd, dd_duration = max_drawdown(equity)
    calmar = ann_return / abs(worst) if worst < 0 else 0.0
    var95, es95 = historical_var_es(rets)
    skew = float(rets.skew()) if len(rets) > 2 else 0.0
    kurt = float(rets.kurtosis()) if len(rets) > 3 else 0.0
    # pandas kurtosis is excess kurtosis; Bailey uses raw kurtosis.
    raw_kurt = kurt + 3
    ci_low, ci_high = bootstrap_sharpe_ci(rets, periods=periods)
    dsr = deflated_sharpe_probability(
        sharpe, n_trials=n_trials, n_obs=max(len(rets), 2), skew=skew, kurtosis=raw_kurt
    )
    bench_sharpe = None
    if benchmark is not None and len(benchmark.dropna()) > 2:
        b = benchmark.dropna()
        bench_sharpe = float(b.mean() / b.std(ddof=1) * _ann_factor(periods)) if b.std(ddof=1) else 0.0
    stats = trade_stats(trades)
    by_year: dict[str, float] = {}
    if not rets.empty and isinstance(rets.index, pd.DatetimeIndex):
        for year, part in rets.groupby(rets.index.year):
            by_year[str(year)] = float((1 + part).prod() - 1)
    return {
        "annualized_return": ann_return,
        "volatility": vol,
        "sharpe": sharpe,
        "sharpe_ci90": [ci_low, ci_high],
        "deflated_sharpe_probability": dsr,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": worst,
        "average_drawdown": average_dd,
        "drawdown_duration_sessions": dd_duration,
        "tail_loss_var_5": var95,
        "expected_shortfall_5": es95,
        "skew": skew,
        "excess_kurtosis": kurt,
        "transaction_costs": costs,
        "slippage": slippage,
        "benchmark_sharpe": bench_sharpe,
        "n_trials": n_trials,
        "return_by_year": by_year,
        **stats,
    }


def monte_carlo_max_drawdown(trades: pd.DataFrame, *, paths: int = 200, seed: int = 11) -> dict[str, float]:
    if trades.empty:
        return {"median_max_drawdown": 0, "p95_max_drawdown": 0}
    rng = np.random.default_rng(seed)
    pnl = trades["pnl"].to_numpy()
    worsts = []
    for _ in range(paths):
        shuffled = rng.permutation(pnl)
        equity = np.cumsum(shuffled)
        peak = np.maximum.accumulate(equity)
        dd = equity - peak
        worsts.append(float(dd.min()))
    return {
        "median_max_drawdown": float(np.median(worsts)),
        "p95_max_drawdown": float(np.quantile(worsts, 0.05)),
    }
