"""Data integrity checks. The platform must know when its data cannot be trusted."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from quantos.data.calendar import is_session, sessions_between


def integrity_report(
    frame: pd.DataFrame,
    *,
    start: date,
    end: date,
    jump_threshold: float = 0.4,
    now: datetime | None = None,
    stale_after_sessions: int = 5,
) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    if frame.empty:
        return {"trustworthy": False, "issues": [{"kind": "empty", "detail": "no rows"}]}

    required = {"symbol", "session_date", "open", "high", "low", "close", "volume", "source"}
    missing_cols = sorted(required - set(frame.columns))
    if missing_cols:
        issues.append({"kind": "schema", "detail": ",".join(missing_cols)})

    work = frame.copy()
    work["session_date"] = pd.to_datetime(work["session_date"]).dt.date
    dupes = work.duplicated(["symbol", "session_date", "source"], keep=False)
    for _, row in work.loc[dupes].iterrows():
        issues.append(
            {
                "kind": "duplicate",
                "symbol": row["symbol"],
                "session_date": str(row["session_date"]),
            }
        )

    for symbol, group in work.groupby("symbol"):
        observed = set(group["session_date"])
        expected = set(sessions_between(start, end))
        for day in sorted(expected - observed):
            if is_session(day):
                issues.append({"kind": "missing_bar", "symbol": symbol, "session_date": str(day)})
        ordered = group.sort_values("session_date")
        returns = ordered["close"].pct_change()
        for idx, value in returns.items():
            if pd.notna(value) and abs(float(value)) > jump_threshold:
                flagged = ordered.loc[idx]
                if not bool(flagged.get("corporate_action", False)):
                    issues.append(
                        {
                            "kind": "abnormal_jump",
                            "symbol": symbol,
                            "session_date": str(flagged["session_date"]),
                            "return": float(value),
                        }
                    )
        for _, row in ordered.iterrows():
            price_fields = [row["open"], row["high"], row["low"], row["close"]]
            if any(pd.isna(value) or float(value) <= 0 for value in price_fields):
                issues.append(
                    {
                        "kind": "non_positive_price",
                        "symbol": symbol,
                        "session_date": str(row["session_date"]),
                    }
                )
            if float(row["high"]) < max(float(row["open"]), float(row["close"])) or float(row["low"]) > min(
                float(row["open"]), float(row["close"])
            ):
                issues.append(
                    {
                        "kind": "ohlc_inconsistent",
                        "symbol": symbol,
                        "session_date": str(row["session_date"]),
                    }
                )

    clock = now or datetime.now(timezone.utc)
    if "ingest_ts" in work.columns and work["ingest_ts"].notna().any():
        latest = pd.to_datetime(work["ingest_ts"], utc=True).max()
        age_days = (clock - latest.to_pydatetime()).total_seconds() / 86400
        if age_days > stale_after_sessions * 1.5:
            issues.append({"kind": "stale_feed", "age_days": age_days})

    return {
        "trustworthy": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "generated_at": clock.isoformat(),
    }
