"""Read models over the ledger: the period summary and the transaction list.

The queries, the filters and the page contract live here so a router never holds SQL.
"""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.accounts.persistence import accounts_persistence
from app.categories.constants.categories_constants import TRANSFERS_CATEGORY

DEFAULT_PAGE_SIZE = 200
MAXIMUM_PAGE_SIZE = 200

SUMMARY_SQL = """
SELECT
    coalesce(
        sum(CASE WHEN category <> :transfers AND amount_cents > 0 THEN amount_cents END), 0
    ) AS total_in_cents,
    coalesce(
        -sum(CASE WHEN category <> :transfers AND amount_cents < 0 THEN amount_cents END), 0
    ) AS total_out_cents,
    count(*) AS transaction_count
FROM transactions
WHERE posted_date BETWEEN :start AND :end
"""

TRANSACTION_COLUMNS = """
    t.connection_id, t.account_id, a.name AS account_name, t.transaction_id, t.posted_date,
    t.description, t.category, t.amount_cents
"""

TRANSACTION_FROM_SQL = """
FROM transactions t
JOIN accounts a ON a.connection_id = t.connection_id AND a.account_id = t.account_id
"""


class InvalidDateRangeError(ValueError):
    """Both dates are inclusive, so a start after the end matches nothing."""


@dataclass(frozen=True)
class SummaryFigures:
    """The numbers behind the summary; the response model decides how to present them."""

    start: date
    end: date
    total_in_cents: int
    total_out_cents: int
    cash_total_cents: int
    net_worth_cents: int
    transaction_count: int


@dataclass(frozen=True)
class TransactionFilters:
    """The optional filters on the transaction list, each one narrowing the query."""

    account_id: str | None = None
    category: str | None = None
    start: date | None = None
    end: date | None = None
    include_transfers: bool = False


@dataclass(frozen=True)
class TransactionPage:
    """One page of rows plus the total that matches the filters, for the pager."""

    rows: Sequence[sqlite3.Row]
    total: int


def validate_range(start: date | None, end: date | None) -> None:
    """Both dates are inclusive, so a start after the end is a request the caller can fix."""
    if start is not None and end is not None and start > end:
        raise InvalidDateRangeError("start must be on or before end.")


def resolve_summary_range(start: date | None, end: date | None) -> tuple[date, date]:
    """Both dates are inclusive and read in machine local time; the default is the current month."""
    validate_range(start, end)

    today = date.today()

    return start or today.replace(day=1), end or today


def get_summary_figures(connection: sqlite3.Connection, range_start: date, range_end: date) -> SummaryFigures:
    parameters = {
        "transfers": TRANSFERS_CATEGORY,
        "start": range_start.isoformat(),
        "end": range_end.isoformat(),
    }
    row = connection.execute(SUMMARY_SQL, parameters).fetchone()

    return SummaryFigures(
        start=range_start,
        end=range_end,
        total_in_cents=int(row["total_in_cents"]),
        total_out_cents=int(row["total_out_cents"]),
        cash_total_cents=accounts_persistence.get_cash_total_cents(connection),
        net_worth_cents=accounts_persistence.get_net_worth_cents(connection),
        transaction_count=int(row["transaction_count"]),
    )


def find_transaction_page(
    connection: sqlite3.Connection,
    filters: TransactionFilters,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> TransactionPage:
    clauses: list[str] = []
    parameters: list[object] = []

    if filters.account_id is not None:
        clauses.append("t.account_id = ?")
        parameters.append(filters.account_id)

    if filters.category is not None:
        clauses.append("t.category = ?")
        parameters.append(filters.category)

    if filters.start is not None:
        clauses.append("t.posted_date >= ?")
        parameters.append(filters.start.isoformat())

    if filters.end is not None:
        clauses.append("t.posted_date <= ?")
        parameters.append(filters.end.isoformat())

    if not filters.include_transfers:
        clauses.append("t.category <> ?")
        parameters.append(TRANSFERS_CATEGORY)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    total_row = connection.execute(
        f"SELECT count(*) AS total {TRANSACTION_FROM_SQL} {where_sql}", parameters
    ).fetchone()
    rows = connection.execute(
        f"SELECT {TRANSACTION_COLUMNS} {TRANSACTION_FROM_SQL} {where_sql} "
        "ORDER BY t.posted_date DESC, t.transaction_id DESC LIMIT ? OFFSET ?",
        [*parameters, limit, offset],
    ).fetchall()

    return TransactionPage(rows=rows, total=int(total_row["total"]))
