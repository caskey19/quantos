"""Liquidity-conditioned short-horizon reversal. Emits targets. Does not submit orders."""

from __future__ import annotations

from datetime import date

from quantos.contracts.models import MarketStateView, Side, TargetWeight

STRATEGY_NAME = "liquid-short-horizon-reversal"
STRATEGY_VERSION = "0.1.0"


class ReversalStrategy:
    def __init__(
        self,
        lookback: int,
        hold: int,
        *,
        decile: float = 0.1,
        min_dollar_volume: float = 20_000_000,
        max_spread_bps: float = 15.0,
        gross_budget: float = 40_000,
    ) -> None:
        self.lookback = lookback
        self.hold = hold
        self.decile = decile
        self.min_dollar_volume = min_dollar_volume
        self.max_spread_bps = max_spread_bps
        self.gross_budget = gross_budget

    def targets(
        self,
        asof: date,
        cross_section: list[dict],
        state: MarketStateView | None = None,
        *,
        apply_regime_scalar: bool = False,
    ) -> list[TargetWeight]:
        eligible = []
        for row in cross_section:
            if row.get("session_date") != asof:
                continue
            residual = row.get("residual")
            if residual is None:
                continue
            spread = float(row.get("spread_bps") or 0)
            dollar = float(row.get("dollar_volume") or 0)
            if dollar < self.min_dollar_volume or spread > self.max_spread_bps:
                continue
            if not row.get("liquid", True):
                continue
            eligible.append(row)
        if len(eligible) < 10:
            return []
        ranked = sorted(eligible, key=lambda row: float(row["residual"]))
        count = max(1, int(len(ranked) * self.decile))
        losers = ranked[:count]
        winners = ranked[-count:]
        budget = self.gross_budget
        if apply_regime_scalar and state is not None:
            budget *= min(state.exposure_scalar, 1.0)
        per_side = budget / 2
        per_name = per_side / count
        targets: list[TargetWeight] = []
        for row in losers:
            targets.append(
                TargetWeight(
                    symbol=row["symbol"],
                    target_notional=per_name,
                    side=Side.BUY,
                    reason_code="reversal_long_loser",
                    signal_strength=float(row["residual"]),
                    hold_sessions=self.hold,
                    sector=row.get("sector") or "UNKNOWN",
                )
            )
        for row in winners:
            targets.append(
                TargetWeight(
                    symbol=row["symbol"],
                    target_notional=per_name,
                    side=Side.SELL,
                    reason_code="reversal_short_winner",
                    signal_strength=float(row["residual"]),
                    hold_sessions=self.hold,
                    sector=row.get("sector") or "UNKNOWN",
                )
            )
        return targets
