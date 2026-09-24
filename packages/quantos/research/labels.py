"""Forward labels. Importing this from strategy or feature code is a boundary violation."""

from __future__ import annotations

import pandas as pd


def forward_open_return(frame: pd.DataFrame, hold: int) -> pd.DataFrame:
    """Return from the next open to the open `hold` sessions later. Research only."""
    if hold < 1:
        raise ValueError("hold must be positive")
    work = frame.sort_values(["symbol", "session_date"]).copy()
    grouped = work.groupby("symbol", sort=False)["open"]
    entry = grouped.shift(-1)
    exit_px = grouped.shift(-(hold + 1))
    work["forward_return"] = exit_px / entry - 1
    work["label_uses_future"] = True
    return work
