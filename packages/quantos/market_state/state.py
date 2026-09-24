"""Market state. The exposure scalar can only reduce risk, never remove a hard limit."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from quantos.contracts.models import MarketStateView


def classify_market(frame: pd.DataFrame, asof: date, window: int = 20) -> MarketStateView:
    work = frame.copy()
    work.attrs = {}
    work["session_date"] = pd.to_datetime(work["session_date"]).dt.date
    history = work[work["session_date"] <= asof]
    dates = sorted(history["session_date"].unique())
    if len(dates) < 2:
        return MarketStateView(
            asof=asof,
            realized_vol=0,
            trend=0,
            dispersion=0,
            breadth=0.5,
            median_spread_bps=0,
            median_dollar_volume=0,
            regime="insufficient_history",
            exposure_scalar=0.0,
        )
    use_dates = dates[-window:]
    window_frame = history[history["session_date"].isin(use_dates)]
    returns = []
    for _, group in window_frame.groupby("symbol"):
        ordered = group.sort_values("session_date")
        returns.append(ordered["close"].pct_change())
    chunks = [series.dropna().to_numpy() for series in returns]
    stacked = np.concatenate(chunks) if chunks else np.array([])
    daily = window_frame.groupby("session_date")["close"].mean().pct_change().dropna()
    realized = float(daily.std() * np.sqrt(252)) if len(daily) else 0.0
    trend = float(daily.sum()) if len(daily) else 0.0
    dispersion = float(np.std(stacked)) if len(stacked) else 0.0
    last = window_frame[window_frame["session_date"] == dates[-1]]
    prior_date = dates[-2]
    prior = window_frame[window_frame["session_date"] == prior_date][["symbol", "close"]].rename(
        columns={"close": "prior_close"}
    )
    merged = last.merge(prior, on="symbol", how="inner")
    breadth = float((merged["close"] > merged["prior_close"]).mean()) if len(merged) else 0.5
    spread = float(last["spread_bps"].median()) if "spread_bps" in last.columns else 0.0
    dollar = float(last["dollar_volume"].median()) if "dollar_volume" in last.columns else 0.0
    if realized > 0.25:
        regime = "high_vol"
        scalar = 0.5
    elif trend < -0.05:
        regime = "downtrend"
        scalar = 0.75
    elif realized < 0.12 and trend > 0:
        regime = "low_vol_uptrend"
        scalar = 1.0
    else:
        regime = "mixed"
        scalar = 1.0
    return MarketStateView(
        asof=asof,
        realized_vol=realized,
        trend=trend,
        dispersion=dispersion,
        breadth=breadth,
        median_spread_bps=spread,
        median_dollar_volume=dollar,
        regime=regime,
        exposure_scalar=min(scalar, 1.0),
    )
