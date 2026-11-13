"""The period summary and the transaction list: the range rule and the two reads.

A range is two inclusive dates read in machine local time. The default for the summary is
the current month; the list applies filters only where the caller supplied one.
"""

import sqlite3
from datetime import date

from app.transactions.errors.transactions_errors import InvalidDateRangeError
from app.transactions.model.transactions_model import (
    SummaryFigures,
    TransactionFilters,
    TransactionPage,
)
from app.transactions.persistence import transactions_persistence as persistence


def get_summary(connection: sqlite3.Connection, start: date | None, end: date | None) -> SummaryFigures:
    """The figures for `start`..`end` inclusive, defaulting to the current month."""
    range_start, range_end = resolve_summary_range(start, end)

    return persistence.get_summary_figures(connection, range_start, range_end)


def find_transactions(
    connection: sqlite3.Connection,
    filters: TransactionFilters,
    limit: int,
    offset: int,
) -> TransactionPage:
    """One page of transactions matching `filters`."""
    validate_range(filters.start, filters.end)

    return persistence.find_transaction_page(connection, filters, limit, offset)


def validate_range(start: date | None, end: date | None) -> None:
    """Both dates are inclusive, so a start after the end is a request the caller can fix."""
    if start is not None and end is not None and start > end:
        raise InvalidDateRangeError("start must be on or before end.")


def resolve_summary_range(start: date | None, end: date | None) -> tuple[date, date]:
    """Validate the range, then default a missing side to the current month."""
    validate_range(start, end)

    today = date.today()

    return start or today.replace(day=1), end or today
