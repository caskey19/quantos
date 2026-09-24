"""Stream supervisor: reconnects, gaps, duplicates, staleness. No network I/O here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class StreamEvent:
    sequence: int | None
    symbol: str
    kind: str
    exchange_ts: datetime | None
    provider_ts: datetime | None
    receive_ts: datetime
    payload_id: str


@dataclass
class StreamSupervisor:
    stale_after_seconds: float = 15
    reconnects: int = 0
    last_heartbeat: datetime | None = None
    last_sequence: dict[str, int] = field(default_factory=dict)
    seen_ids: set[str] = field(default_factory=set)
    gaps: list[dict[str, object]] = field(default_factory=list)
    duplicates: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    connected: bool = False

    def on_connect(self) -> None:
        self.connected = True
        self.last_heartbeat = datetime.now(timezone.utc)

    def on_disconnect(self) -> None:
        self.connected = False
        self.reconnects += 1

    def heartbeat(self, now: datetime | None = None) -> None:
        self.last_heartbeat = now or datetime.now(timezone.utc)
        self.connected = True

    def stale(self, now: datetime | None = None) -> bool:
        if self.last_heartbeat is None:
            return True
        clock = now or datetime.now(timezone.utc)
        return (clock - self.last_heartbeat).total_seconds() > self.stale_after_seconds

    def observe(self, event: StreamEvent) -> str:
        if event.payload_id in self.seen_ids:
            self.duplicates += 1
            return "duplicate"
        self.seen_ids.add(event.payload_id)
        if event.sequence is not None:
            previous = self.last_sequence.get(event.symbol)
            if previous is not None and event.sequence > previous + 1:
                self.gaps.append(
                    {
                        "symbol": event.symbol,
                        "expected": previous + 1,
                        "got": event.sequence,
                    }
                )
            self.last_sequence[event.symbol] = event.sequence
        if event.exchange_ts is not None:
            self.latencies_ms.append(
                (event.receive_ts - event.exchange_ts).total_seconds() * 1000
            )
        return "accepted"

    def health(self) -> dict[str, object]:
        latency = self.latencies_ms[-1] if self.latencies_ms else None
        return {
            "connected": self.connected and not self.stale(),
            "reconnects": self.reconnects,
            "duplicates": self.duplicates,
            "gaps": len(self.gaps),
            "last_latency_ms": latency,
            "stale": self.stale(),
        }
