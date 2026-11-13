"""The typed shape of an accounts row, built by its own `from_row` so the column names live
next to the fields they fill."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    connection_id: str
    account_id: str
    connection_name: str
    name: str
    currency: str
    balance_cents: int
    available_balance_cents: int | None
    balance_date: str
    include_in_cash: bool

    @staticmethod
    def from_row(row: sqlite3.Row) -> "Account":
        return Account(
            connection_id=str(row["connection_id"]),
            account_id=str(row["account_id"]),
            connection_name=str(row["connection_name"]),
            name=str(row["name"]),
            currency=str(row["currency"]),
            balance_cents=int(row["balance_cents"]),
            available_balance_cents=(
                None if row["available_balance_cents"] is None else int(row["available_balance_cents"])
            ),
            balance_date=str(row["balance_date"]),
            include_in_cash=bool(row["include_in_cash"]),
        )
