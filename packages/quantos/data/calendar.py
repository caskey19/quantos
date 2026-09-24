"""NYSE session calendar.

Fixed-date holidays follow the standard observed-weekday rule.
Good Friday is an explicit list because it is not a US federal holiday.
One-off closure days are omitted rather than guessed. Verify this file
against the exchange notice before using it for a production backtest.
"""

from __future__ import annotations

from datetime import date, timedelta

GOOD_FRIDAY = {
    date(2022, 4, 15),
    date(2023, 4, 7),
    date(2024, 3, 29),
    date(2025, 4, 18),
    date(2026, 4, 3),
    date(2027, 3, 26),
}


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    shift = (weekday - first.weekday()) % 7
    return first + timedelta(days=shift + 7 * (n - 1))


def _last_monday(year: int, month: int) -> date:
    if month == 12:
        cursor = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        cursor = date(year, month + 1, 1) - timedelta(days=1)
    while cursor.weekday() != 0:
        cursor -= timedelta(days=1)
    return cursor


def holidays_for_year(year: int) -> set[date]:
    days = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _observed(date(year, 6, 19)),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
        _last_monday(year, 5),
    }
    days.update(day for day in GOOD_FRIDAY if day.year == year)
    return days


def is_session(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    return day not in holidays_for_year(day.year)


def sessions_between(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if is_session(cursor):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def next_session(day: date, steps: int = 1) -> date:
    if steps < 1:
        raise ValueError("steps must be positive")
    cursor = day
    seen = 0
    while seen < steps:
        cursor += timedelta(days=1)
        if is_session(cursor):
            seen += 1
    return cursor


def previous_sessions(day: date, count: int) -> list[date]:
    found: list[date] = []
    cursor = day
    while len(found) < count:
        cursor -= timedelta(days=1)
        if is_session(cursor):
            found.append(cursor)
    found.reverse()
    return found
