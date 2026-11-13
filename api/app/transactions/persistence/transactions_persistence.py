"""Every SQL statement about reading transactions through the API.

One function, one statement, and no decisions: the filter clauses are the only thing built
here, and the page total travels with the transactions so a caller cannot report one without
the other. Reads come back as `Transaction`, never as a raw row.
"""

import sqlite3
from datetime import date

from app.accounts.persistence import accounts_persistence
from app.categories.constants.categories_constants import TRANSFERS_CATEGORY
from app.transactions.constants.transactions_constants import DEFAULT_PAGE_SIZE
from app.transactions.model.transactions_model import (
    SummaryFigures,
    Transaction,
    TransactionFilters,
    TransactionPage,
    TransactionRecord,
)

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

UPSERT_TRANSACTION_SQL = """
INSERT INTO transactions (
    connection_id, account_id, transaction_id, posted_at, posted_date, transacted_at,
    description, amount_cents, category, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (connection_id, account_id, transaction_id) DO UPDATE SET
    posted_at = excluded.posted_at,
    posted_date = excluded.posted_date,
    transacted_at = excluded.transacted_at,
    description = excluded.description,
    amount_cents = excluded.amount_cents,
    category = excluded.category,
    updated_at = excluded.updated_at
"""

COUNT_TRANSACTIONS_SQL = "SELECT count(*) AS total FROM transactions"

TRANSACTION_COLUMNS = """
    t.connection_id, t.account_id, a.name AS account_name, t.transaction_id, t.posted_date,
    t.description, t.category, t.amount_cents
"""

TRANSACTION_FROM_SQL = """
FROM transactions t
JOIN accounts a ON a.connection_id = t.connection_id AND a.account_id = t.account_id
"""


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
    transactions = connection.execute(
        f"SELECT {TRANSACTION_COLUMNS} {TRANSACTION_FROM_SQL} {where_sql} "
        "ORDER BY t.posted_date DESC, t.transaction_id DESC LIMIT ? OFFSET ?",
        [*parameters, limit, offset],
    ).fetchall()

    return TransactionPage(
        transactions=[Transaction.from_row(row) for row in transactions], total=int(total_row["total"])
    )


def upsert_transaction(connection: sqlite3.Connection, record: TransactionRecord, fetched_at: str) -> None:
    connection.execute(
        UPSERT_TRANSACTION_SQL,
        (
            record.connection_id,
            record.account_id,
            record.transaction_id,
            record.posted_at,
            record.posted_date,
            record.transacted_at,
            record.description,
            record.amount_cents,
            record.category,
            fetched_at,
            fetched_at,
        ),
    )


def count_transactions(connection: sqlite3.Connection) -> int:
    return int(connection.execute(COUNT_TRANSACTIONS_SQL).fetchone()["total"])
