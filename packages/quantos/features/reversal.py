"""Past-only reversal features. Labels live in quantos.research.labels."""

from __future__ import annotations

import pandas as pd


def reversal_features(frame: pd.DataFrame, lookback: int) -> pd.DataFrame:
    if lookback < 1:
        raise ValueError("lookback must be positive")
    work = frame.sort_values(["symbol", "session_date"]).copy()
    work["session_date"] = pd.to_datetime(work["session_date"]).dt.date
    work["past_return"] = work.groupby("symbol", sort=False)["close"].pct_change(lookback)
    work["cs_mean"] = work.groupby("session_date", sort=False)["past_return"].transform("mean")
    work["residual"] = work["past_return"] - work["cs_mean"]
    work["feature_asof"] = work["session_date"]
    keep = [
        "symbol",
        "session_date",
        "feature_asof",
        "past_return",
        "residual",
        "close",
        "open",
        "high",
        "low",
        "volume",
        "dollar_volume",
        "spread_bps",
        "sector",
        "liquid",
        "bid",
        "ask",
    ]
    present = [column for column in keep if column in work.columns]
    return work[present]
