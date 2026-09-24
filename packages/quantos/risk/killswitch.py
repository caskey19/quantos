"""Kill switches. They stop new risk. They do not blindly liquidate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from quantos.contracts.models import KillAction, KillReason, OrderIntent, Side


@dataclass
class KillSwitch:
    action: KillAction = KillAction.STOP_NEW
    tripped: bool = False
    reason: KillReason | None = None
    detail: str = ""
    tripped_at: datetime | None = None
    history: list[dict[str, str]] = field(default_factory=list)

    def trip(self, reason: KillReason, detail: str = "", action: KillAction | None = None) -> None:
        self.tripped = True
        self.reason = reason
        self.detail = detail
        if action is not None:
            self.action = action
        self.tripped_at = datetime.now(timezone.utc)
        self.history.append(
            {
                "reason": reason.value,
                "detail": detail,
                "action": self.action.value,
                "at": self.tripped_at.isoformat(),
            }
        )

    def reset_requires_operator(self) -> None:
        """Operator-only. Automated code paths must not call this after a loss or data kill."""
        self.tripped = False
        self.reason = None
        self.detail = ""

    def blocks(self, intent: OrderIntent, position_qty: float) -> str | None:
        if not self.tripped:
            return None
        if self.action == KillAction.REDUCE_ONLY:
            reducing = (intent.side == Side.SELL and position_qty > 0) or (
                intent.side == Side.BUY and position_qty < 0
            )
            if reducing and abs(intent.qty) <= abs(position_qty) + 1e-9:
                return None
            return f"kill switch {self.reason.value} allows reduce-only orders"
        return f"kill switch {self.reason.value}: {self.action.value}"

    def status(self) -> dict[str, object]:
        return {
            "tripped": self.tripped,
            "reason": self.reason.value if self.reason else None,
            "action": self.action.value,
            "detail": self.detail,
        }
