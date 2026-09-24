"""Strategy lifecycle. Nothing in this module can enter a live state."""

from __future__ import annotations

from quantos.contracts.models import LIVE_STATES, StrategyState

_FORWARD: dict[StrategyState, set[StrategyState]] = {
    StrategyState.IDEA: {StrategyState.RESEARCHING, StrategyState.REJECTED},
    StrategyState.RESEARCHING: {StrategyState.REJECTED, StrategyState.BACKTESTED},
    StrategyState.BACKTESTED: {StrategyState.REJECTED, StrategyState.VALIDATED, StrategyState.RESEARCHING},
    StrategyState.VALIDATED: {StrategyState.REJECTED, StrategyState.PAPER, StrategyState.SUSPENDED},
    StrategyState.PAPER: {StrategyState.REJECTED, StrategyState.SHADOW, StrategyState.SUSPENDED},
    StrategyState.SHADOW: {StrategyState.REJECTED, StrategyState.SUSPENDED},
    StrategyState.LIMITED_LIVE: {StrategyState.SUSPENDED, StrategyState.RETIRED},
    StrategyState.PRODUCTION: {StrategyState.SUSPENDED, StrategyState.RETIRED},
    StrategyState.SUSPENDED: {StrategyState.RETIRED, StrategyState.RESEARCHING},
    StrategyState.REJECTED: {StrategyState.RETIRED, StrategyState.RESEARCHING},
    StrategyState.RETIRED: set(),
}


class PromotionError(RuntimeError):
    pass


def promote(current: StrategyState, target: StrategyState, *, evidence_note: str) -> StrategyState:
    if target in LIVE_STATES:
        raise PromotionError(
            "Automatic promotion into live trading is forbidden. "
            "Limited live requires the manual checklist, which this function cannot complete."
        )
    if not evidence_note.strip():
        raise PromotionError("Promotion requires a written evidence note.")
    allowed = _FORWARD.get(current, set())
    if target not in allowed:
        raise PromotionError(f"Cannot move {current.value} to {target.value}")
    return target
