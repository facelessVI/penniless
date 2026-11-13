"""The period summary and the transaction list: the range rule and the two reads.

A range is two inclusive dates read in machine local time. The default for the summary is
the current month; the list applies filters only where the caller supplied one.
"""

import sqlite3
from datetime import UTC, date, datetime

from app.categories.model.categories_model import CategoryRules
from app.common.dates import local_date
from app.common.errors import SimpleFinError
from app.common.money import parse_cents
from app.common.simplefin_api import SimpleFinAccount
from app.transactions.errors.transactions_errors import InvalidDateRangeError
from app.transactions.model.transactions_model import (
    SummaryFigures,
    TransactionFilters,
    TransactionPage,
    TransactionRecord,
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


def is_storable(transaction_posted: int | None, pending: bool) -> bool:
    """Pending rows never appear in v0 responses, and a 0 posted date means "not posted yet"."""
    return not pending and transaction_posted is not None and transaction_posted > 0


def upsert_transactions(
    connection: sqlite3.Connection,
    account: SimpleFinAccount,
    connection_id: str,
    fetched_at: str,
    rules: CategoryRules,
) -> int:
    """Store the account's storable transactions, classified at write time. Returns how many.

    Classification happens here rather than in a later pass: a transaction is never visible
    unclassified because of a missing re-classify.
    """
    stored = 0

    for transaction in account.transactions:
        posted_epoch = transaction.posted

        if not is_storable(posted_epoch, transaction.pending) or posted_epoch is None:
            continue

        amount_cents = parse_cents(transaction.amount)

        if amount_cents is None:
            raise SimpleFinError(f"SimpleFIN transaction {transaction.id} reported no amount.")

        record = TransactionRecord(
            connection_id=connection_id,
            account_id=account.id,
            transaction_id=transaction.id,
            posted_at=datetime.fromtimestamp(posted_epoch, UTC).isoformat(timespec="seconds"),
            posted_date=local_date(posted_epoch).isoformat(),
            transacted_at=local_date(transaction.transacted_at).isoformat() if transaction.transacted_at else None,
            description=transaction.description,
            amount_cents=amount_cents,
            category=rules.classify(transaction.description),
        )

        persistence.upsert_transaction(connection, record, fetched_at)
        stored += 1

    return stored
