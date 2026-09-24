"""Structured logs and a small in-process metric buffer."""

from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4

import psutil

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_SECRET = re.compile(r"(api[_-]?key|secret|password|token|authorization)", re.IGNORECASE)


def new_correlation_id() -> str:
    value = uuid4().hex
    correlation_id.set(value)
    return value


def redact(payload: dict) -> dict:
    clean = {}
    for key, value in payload.items():
        if _SECRET.search(str(key)):
            clean[key] = "***"
        elif isinstance(value, dict):
            clean[key] = redact(value)
        else:
            clean[key] = value
    return clean


def log_event(event: str, **fields: object) -> dict:
    record = redact(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "correlation_id": correlation_id.get(),
            **fields,
        }
    )
    logging.getLogger("quantos").info(json.dumps(record, default=str))
    return record


class LatencyLog:
    def __init__(self) -> None:
        self.samples: dict[str, list[float]] = {}

    def observe(self, stage: str, milliseconds: float) -> None:
        self.samples.setdefault(stage, []).append(milliseconds)

    def snapshot(self) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        for stage, values in self.samples.items():
            out[stage] = values[-1] if values else None
        return out


def process_health() -> dict[str, float]:
    process = psutil.Process()
    memory = process.memory_info().rss / (1024 * 1024)
    return {"cpu_percent": process.cpu_percent(interval=0.0), "memory_mb": memory}
