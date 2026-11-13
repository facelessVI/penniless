"""Every SQL statement about accounts and their balances.

One function, one statement, and no decisions: a miss comes back as `None`, and the service
or router decides what that means. Reads come back as `AccountRow`, never as a raw row.
"""

import sqlite3

from app.accounts.model.accounts_model import AccountRow
from app.common import db

ACCOUNT_COLUMNS = """
    connection_id, account_id, connection_name, name, currency, balance_cents,
    available_balance_cents, balance_date, include_in_cash
"""

SELECT_ACCOUNTS_SQL = f"SELECT {ACCOUNT_COLUMNS} FROM accounts ORDER BY connection_name, name"

SELECT_ACCOUNT_SQL = f"SELECT {ACCOUNT_COLUMNS} FROM accounts WHERE connection_id = ? AND account_id = ?"

UPDATE_INCLUDE_IN_CASH_SQL = """
UPDATE accounts SET include_in_cash = ?, updated_at = ? WHERE connection_id = ? AND account_id = ?
"""

CASH_TOTAL_SQL = "SELECT coalesce(sum(balance_cents), 0) AS cash_total_cents FROM accounts WHERE include_in_cash = 1"

NET_WORTH_SQL = "SELECT coalesce(sum(balance_cents), 0) AS net_worth_cents FROM accounts"

COUNT_ACCOUNTS_SQL = "SELECT count(*) AS total FROM accounts"


def get_accounts(connection: sqlite3.Connection) -> list[AccountRow]:
    return [AccountRow.from_row(row) for row in connection.execute(SELECT_ACCOUNTS_SQL)]


def get_account(connection: sqlite3.Connection, connection_id: str, account_id: str) -> AccountRow | None:
    row = connection.execute(SELECT_ACCOUNT_SQL, (connection_id, account_id)).fetchone()

    return None if row is None else AccountRow.from_row(row)


def set_account_included_in_cash(
    connection: sqlite3.Connection, connection_id: str, account_id: str, include_in_cash: bool
) -> AccountRow | None:
    """Write the toggle and return the updated row, or `None` when no account matched."""
    with connection:
        cursor = connection.execute(
            UPDATE_INCLUDE_IN_CASH_SQL,
            (int(include_in_cash), db.now_iso(), connection_id, account_id),
        )

    if cursor.rowcount == 0:
        return None

    return get_account(connection, connection_id, account_id)


def get_cash_total_cents(connection: sqlite3.Connection) -> int:
    return int(connection.execute(CASH_TOTAL_SQL).fetchone()["cash_total_cents"])


def get_net_worth_cents(connection: sqlite3.Connection) -> int:
    return int(connection.execute(NET_WORTH_SQL).fetchone()["net_worth_cents"])


def count_accounts(connection: sqlite3.Connection) -> int:
    return int(connection.execute(COUNT_ACCOUNTS_SQL).fetchone()["total"])
