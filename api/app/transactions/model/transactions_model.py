"""The typed shapes of the transactions table and the results the endpoints return.

Every stored row comes back as a `TransactionRow` built by its own `from_row`, so the
column names live next to the fields they fill.
"""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TransactionRow:
    """One stored transaction, with its account's name joined in for the list."""

    connection_id: str
    account_id: str
    account_name: str
    transaction_id: str
    posted_date: str
    description: str
    category: str
    amount_cents: int

    @staticmethod
    def from_row(row: sqlite3.Row) -> "TransactionRow":
        return TransactionRow(
            connection_id=str(row["connection_id"]),
            account_id=str(row["account_id"]),
            account_name=str(row["account_name"]),
            transaction_id=str(row["transaction_id"]),
            posted_date=str(row["posted_date"]),
            description=str(row["description"]),
            category=str(row["category"]),
            amount_cents=int(row["amount_cents"]),
        )


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

    rows: Sequence[TransactionRow]
    total: int
