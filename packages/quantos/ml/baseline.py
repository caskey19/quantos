"""Linear baseline. A model is stored and left unpromoted unless it wins after costs."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd


def fit_linear_baseline(frame: pd.DataFrame, train_end: str) -> dict:
    work = frame.dropna(subset=["residual", "forward_return"]).copy()
    train = work[work["session_date"].astype(str) < train_end]
    valid = work[work["session_date"].astype(str) >= train_end]
    if len(train) < 20 or len(valid) < 20:
        return {"promoted": False, "reason": "insufficient rows", "version": "linear-0"}
    x_train = np.column_stack([np.ones(len(train)), train["residual"].to_numpy()])
    y_train = train["forward_return"].to_numpy()
    coef, *_ = np.linalg.lstsq(x_train, y_train, rcond=None)
    x_valid = np.column_stack([np.ones(len(valid)), valid["residual"].to_numpy()])
    pred = x_valid @ coef
    actual = valid["forward_return"].to_numpy()
    ss_res = float(np.sum((actual - pred) ** 2))
    ss_tot = float(np.sum((actual - actual.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return {
        "version": "linear-residual-0.1.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": ["residual"],
        "hyperparameters": {"fit": "ols"},
        "coefficients": {"intercept": float(coef[0]), "residual": float(coef[1])},
        "validation_r2": r2,
        "promoted": False,
        "reason": "kept only as a baseline; promotion requires a costed out-of-sample improvement that this run does not grant",
        "calibration": "not a probability model",
    }
