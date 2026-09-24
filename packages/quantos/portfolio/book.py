"""Portfolio exposures. Sizing up is not this layer's job."""

from __future__ import annotations

from quantos.contracts.models import PositionView


def exposures(positions: list[PositionView]) -> dict[str, float]:
    gross = sum(abs(item.notional) for item in positions)
    net = sum(item.notional for item in positions)
    return {"gross": gross, "net": net, "count": float(len(positions))}
