"""Read models over the ledger: accounts, the period summary, and the transaction list.

The queries, the filters and the page contract live here so a router never holds SQL.
Anything that answers a question about stored money belongs in this module; writing
money belongs to `ingest`.
"""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app import categorize, db

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

CASH_TOTAL_SQL = "SELECT coalesce(sum(balance_cents), 0) AS cash_total_cents FROM accounts WHERE include_in_cash = 1"

NET_WORTH_SQL = "SELECT coalesce(sum(balance_cents), 0) AS net_worth_cents FROM accounts"

ACCOUNT_COLUMNS = """
    connection_id, account_id, connection_name, name, currency, balance_cents,
    available_balance_cents, balance_date, include_in_cash
"""

SELECT_ACCOUNTS_SQL = f"SELECT {ACCOUNT_COLUMNS} FROM accounts ORDER BY connection_name, name"

SELECT_ACCOUNT_SQL = f"SELECT {ACCOUNT_COLUMNS} FROM accounts WHERE connection_id = ? AND account_id = ?"

UPDATE_INCLUDE_IN_CASH_SQL = """
UPDATE accounts SET include_in_cash = ?, updated_at = ? WHERE connection_id = ? AND account_id = ?
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
        "transfers": categorize.TRANSFERS_CATEGORY,
        "start": range_start.isoformat(),
        "end": range_end.isoformat(),
    }
    row = connection.execute(SUMMARY_SQL, parameters).fetchone()
    cash_row = connection.execute(CASH_TOTAL_SQL).fetchone()
    net_worth_row = connection.execute(NET_WORTH_SQL).fetchone()

    return SummaryFigures(
        start=range_start,
        end=range_end,
        total_in_cents=int(row["total_in_cents"]),
        total_out_cents=int(row["total_out_cents"]),
        cash_total_cents=int(cash_row["cash_total_cents"]),
        net_worth_cents=int(net_worth_row["net_worth_cents"]),
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
        parameters.append(categorize.TRANSFERS_CATEGORY)

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


def get_accounts(connection: sqlite3.Connection) -> Sequence[sqlite3.Row]:
    return connection.execute(SELECT_ACCOUNTS_SQL).fetchall()


def get_account(connection: sqlite3.Connection, connection_id: str, account_id: str) -> sqlite3.Row | None:
    return connection.execute(SELECT_ACCOUNT_SQL, (connection_id, account_id)).fetchone()


def set_account_included_in_cash(
    connection: sqlite3.Connection, connection_id: str, account_id: str, include_in_cash: bool
) -> sqlite3.Row | None:
    """Write the toggle and return the updated row, or `None` when no account matched."""
    with connection:
        cursor = connection.execute(
            UPDATE_INCLUDE_IN_CASH_SQL,
            (int(include_in_cash), db.now_iso(), connection_id, account_id),
        )

    if cursor.rowcount == 0:
        return None

    return get_account(connection, connection_id, account_id)
