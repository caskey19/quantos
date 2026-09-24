"""Corporate actions. Adjusted series are new files; raw rows stay untouched."""

from __future__ import annotations

from datetime import date

import pandas as pd


def apply_splits(raw: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """Backward-adjust prices and volumes for splits. `splits.ratio` is new/old shares."""
    frame = raw.copy()
    frame["session_date"] = pd.to_datetime(frame["session_date"]).dt.date
    if splits.empty:
        return frame
    for _, split in splits.iterrows():
        symbol = split["symbol"]
        ex_date = split["ex_date"]
        if not isinstance(ex_date, date):
            ex_date = pd.to_datetime(ex_date).date()
        ratio = float(split["ratio"])
        mask = (frame["symbol"] == symbol) & (frame["session_date"] < ex_date)
        for column in ("open", "high", "low", "close"):
            frame.loc[mask, column] = frame.loc[mask, column] / ratio
        if "bid" in frame.columns:
            frame.loc[mask, "bid"] = frame.loc[mask, "bid"] / ratio
            frame.loc[mask, "ask"] = frame.loc[mask, "ask"] / ratio
        frame.loc[mask, "volume"] = frame.loc[mask, "volume"] * ratio
    frame["adjustment"] = "split"
    return frame


def apply_position_split(qty: float, avg_price: float, ratio: float) -> tuple[float, float]:
    return qty * ratio, avg_price / ratio


def cash_dividend(qty: float, amount: float) -> float:
    return qty * amount
