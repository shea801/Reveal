"""Shared date selection helpers for financial statement access."""

import datetime as dt
from collections.abc import Iterable


def parse_iso_date(value: str | dt.datetime | dt.date) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time())
    if not isinstance(value, str):
        raise ValueError("date must be a string in format YYYY-MM-DD")
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must be a string in format YYYY-MM-DD") from exc


def normalize_statement_dates(values: Iterable) -> list[dt.datetime]:
    dates = []
    for value in values:
        if value is None:
            continue
        try:
            dates.append(parse_iso_date(value))
        except ValueError:
            continue
    return sorted(set(dates))


def select_statement_date(
        available_dates: Iterable,
        requested_date: str | dt.datetime | dt.date | None = None,
        quarterly: bool = False,
    ) -> str:
    """
    Select the best fiscal statement date from available dates.

    Annual and quarterly statements select the latest fiscal period on or
    before the requested date. The ``quarterly`` argument remains accepted for
    compatibility but does not change the selection rule.

    When the requested date precedes all available fiscal periods, the earliest
    available period is returned for backward compatibility. Strict
    point-in-time backtests must treat that boundary case as unavailable rather
    than using the returned future period.
    """
    dates = normalize_statement_dates(available_dates)
    if not dates:
        raise ValueError("No valid fiscal dates found")

    if requested_date is None:
        return dates[-1].strftime("%Y-%m-%d")

    requested = parse_iso_date(requested_date)
    if requested in dates:
        return requested.strftime("%Y-%m-%d")

    for date in dates:
        if date < requested:
            continue
        if date == requested:
            return date.strftime("%Y-%m-%d")
        if date > requested:
            idx = dates.index(date)
            if idx > 0:
                prev_date = dates[idx - 1]
            else:
                return dates[0].strftime("%Y-%m-%d")
            if requested > prev_date:
                return prev_date.strftime("%Y-%m-%d")

    return dates[-1].strftime("%Y-%m-%d")

