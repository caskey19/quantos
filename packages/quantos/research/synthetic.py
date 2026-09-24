"""Synthetic panel for methodology tests. This is not market evidence."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from quantos.data.calendar import sessions_between


def synthetic_panel(
    *,
    start: date = date(2022, 1, 3),
    end: date = date(2024, 6, 28),
    n_liquid: int = 30,
    n_illiquid: int = 8,
    seed: int = 7,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = sessions_between(start, end)
    market = rng.normal(0.0002, 0.01, size=len(dates))
    rows: list[dict] = []
    specs = [("L", n_liquid, True, 0.0005, 50_000_000, 0.04, 0.012)] + [
        ("I", n_illiquid, False, 0.008, 500_000, 0.35, 0.03)
    ]
    for prefix, count, liquid, spread, dollar, bounce, idio_scale in specs:
        for index in range(count):
            symbol = f"{prefix}{index:02d}"
            price = float(rng.uniform(20, 150))
            lag = 0.0
            for day_index, session in enumerate(dates):
                idio = float(rng.normal(0, idio_scale))
                shock = -bounce * lag + idio + 0.8 * float(market[day_index])
                open_px = price * (1 + float(rng.normal(0, 0.002)))
                close_px = max(0.5, open_px * (1 + shock))
                high = max(open_px, close_px) * (1 + abs(float(rng.normal(0, 0.002))))
                low = min(open_px, close_px) * (1 - abs(float(rng.normal(0, 0.002))))
                volume = dollar / close_px
                half = close_px * spread / 2
                lag = shock - float(market[day_index])
                rows.append(
                    {
                        "symbol": symbol,
                        "session_date": session,
                        "open": open_px,
                        "high": high,
                        "low": max(low, 0.1),
                        "close": close_px,
                        "volume": volume,
                        "dollar_volume": dollar,
                        "bid": close_px - half,
                        "ask": close_px + half,
                        "spread_bps": spread * 10_000,
                        "sector": "TECH" if index % 2 == 0 else "HEALTH",
                        "source": "synthetic",
                        "adjustment": "raw",
                        "liquid": liquid,
                    }
                )
                price = close_px
    frame = pd.DataFrame(rows)
    return frame
