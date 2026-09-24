"""Sealed final window. Research loaders cannot see it."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml


class SealedWindowError(RuntimeError):
    pass


class SealedWindow:
    def __init__(self, start: date, end: date) -> None:
        self.start = start
        self.end = end

    @classmethod
    def from_file(cls, path: Path) -> "SealedWindow":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            start=date.fromisoformat(payload["sealed_start"]),
            end=date.fromisoformat(payload["sealed_end"]),
        )

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def assert_research_dates(self, days: list[date], purpose: str) -> None:
        if purpose == "promotion_review":
            return
        leaked = [day for day in days if self.contains(day)]
        if leaked:
            raise SealedWindowError(
                f"Sealed holdout dates requested for purpose={purpose}: {leaked[0]} .. {leaked[-1]}"
            )

    def research_mask(self, days: list[date], purpose: str) -> list[date]:
        self.assert_research_dates(days, purpose)
        return [day for day in days if not self.contains(day)]
