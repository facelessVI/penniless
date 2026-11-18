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
    display_name: str | None
    description: str | None
    currency: str
    balance_cents: int
    available_balance_cents: int | None
    balance_date: str
    include_in_cash: bool
    source: int
    labels: tuple[str, ...] = ()

    @staticmethod
    def from_row(row: sqlite3.Row) -> "Account":
        return Account(
            connection_id=str(row["connection_id"]),
            account_id=str(row["account_id"]),
            connection_name=str(row["connection_name"]),
            name=str(row["name"]),
            display_name=None if row["display_name"] is None else str(row["display_name"]),
            description=None if row["description"] is None else str(row["description"]),
            currency=str(row["currency"]),
            balance_cents=int(row["balance_cents"]),
            available_balance_cents=(
                None if row["available_balance_cents"] is None else int(row["available_balance_cents"])
            ),
            balance_date=str(row["balance_date"]),
            include_in_cash=bool(row["include_in_cash"]),
            source=int(row["source"]),
        )


@dataclass(frozen=True)
class AccountChanges:
    """The fields one update carries: `None` means the caller did not supply that field.

    `labels` is the account's complete set, not a delta: an empty tuple clears every label. A zero
    balance is a supplied value, since only `None` means "leave it alone".
    """

    display_name: str | None = None
    description: str | None = None
    include_in_cash: bool | None = None
    labels: tuple[str, ...] | None = None
    balance_cents: int | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.display_name is None
            and self.description is None
            and self.include_in_cash is None
            and self.labels is None
            and self.balance_cents is None
        )
