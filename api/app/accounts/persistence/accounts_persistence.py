"""Every SQL statement about accounts and their balances.

One function, one statement, and no decisions: a miss comes back as `None`, and the service
decides what that means. Reads come back as `Account`, never as a raw row. The transaction
boundary belongs to the service, which is why nothing here opens one.
"""

import sqlite3

from app.accounts.model.accounts_model import Account
from app.common import db

ACCOUNT_COLUMNS = """
    connection_id, account_id, connection_name, name, display_name, description, currency,
    balance_cents, available_balance_cents, balance_date, include_in_cash
"""

SELECT_ACCOUNTS_SQL = f"SELECT {ACCOUNT_COLUMNS} FROM accounts ORDER BY connection_name, coalesce(display_name, name)"

SELECT_ACCOUNT_SQL = f"SELECT {ACCOUNT_COLUMNS} FROM accounts WHERE connection_id = ? AND account_id = ?"

UPDATE_ACCOUNT_SQL = """
UPDATE accounts SET display_name = ?, description = ?, include_in_cash = ?, updated_at = ?
WHERE connection_id = ? AND account_id = ?
"""

CASH_TOTAL_SQL = "SELECT coalesce(sum(balance_cents), 0) AS cash_total_cents FROM accounts WHERE include_in_cash = 1"

NET_WORTH_SQL = "SELECT coalesce(sum(balance_cents), 0) AS net_worth_cents FROM accounts"

UPSERT_ACCOUNT_SQL = """
INSERT INTO accounts (
    connection_id, account_id, connection_name, name, currency, balance_cents,
    available_balance_cents, balance_date, include_in_cash, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (connection_id, account_id) DO UPDATE SET
    connection_name = excluded.connection_name,
    name = excluded.name,
    currency = excluded.currency,
    balance_cents = excluded.balance_cents,
    available_balance_cents = excluded.available_balance_cents,
    balance_date = excluded.balance_date,
    updated_at = excluded.updated_at
"""

UPSERT_ACCOUNT_BALANCE_SQL = """
INSERT INTO account_balances (
    connection_id, account_id, balance_date, balance_cents, available_balance_cents, recorded_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (connection_id, account_id, balance_date) DO UPDATE SET
    balance_cents = excluded.balance_cents,
    available_balance_cents = excluded.available_balance_cents,
    recorded_at = excluded.recorded_at
"""

COUNT_ACCOUNTS_SQL = "SELECT count(*) AS total FROM accounts"

SELECT_LABELS_SQL = """
SELECT label FROM account_labels
WHERE connection_id = ? AND account_id = ?
ORDER BY label COLLATE NOCASE, label
"""

SELECT_LABELS_BY_ACCOUNT_SQL = """
SELECT connection_id, account_id, label FROM account_labels
ORDER BY connection_id, account_id, label COLLATE NOCASE, label
"""

SELECT_LABEL_SQL = "SELECT name FROM labels WHERE name = ? COLLATE NOCASE"

INSERT_LABEL_SQL = "INSERT INTO labels (name) VALUES (?) ON CONFLICT DO NOTHING"

INSERT_ACCOUNT_LABEL_SQL = """
INSERT INTO account_labels (connection_id, account_id, label, created_at) VALUES (?, ?, ?, ?)
"""

DELETE_ACCOUNT_LABELS_SQL = "DELETE FROM account_labels WHERE connection_id = ? AND account_id = ?"

DELETE_ORPHAN_LABELS_SQL = """
DELETE FROM labels WHERE NOT EXISTS (SELECT 1 FROM account_labels WHERE account_labels.label = labels.name)
"""


def get_accounts(connection: sqlite3.Connection) -> list[Account]:
    return [Account.from_row(row) for row in connection.execute(SELECT_ACCOUNTS_SQL)]


def get_account(connection: sqlite3.Connection, connection_id: str, account_id: str) -> Account | None:
    row = connection.execute(SELECT_ACCOUNT_SQL, (connection_id, account_id)).fetchone()

    return None if row is None else Account.from_row(row)


def update_account(connection: sqlite3.Connection, account: Account) -> None:
    """Write the three editable columns of one account."""
    connection.execute(
        UPDATE_ACCOUNT_SQL,
        (
            account.display_name,
            account.description,
            int(account.include_in_cash),
            db.now_iso(),
            account.connection_id,
            account.account_id,
        ),
    )


def get_cash_total_cents(connection: sqlite3.Connection) -> int:
    return int(connection.execute(CASH_TOTAL_SQL).fetchone()["cash_total_cents"])


def get_net_worth_cents(connection: sqlite3.Connection) -> int:
    return int(connection.execute(NET_WORTH_SQL).fetchone()["net_worth_cents"])


def count_accounts(connection: sqlite3.Connection) -> int:
    return int(connection.execute(COUNT_ACCOUNTS_SQL).fetchone()["total"])


def get_account_labels(connection: sqlite3.Connection, connection_id: str, account_id: str) -> tuple[str, ...]:
    rows = connection.execute(SELECT_LABELS_SQL, (connection_id, account_id))

    return tuple(str(row["label"]) for row in rows)


def get_labels_by_account(connection: sqlite3.Connection) -> dict[tuple[str, str], tuple[str, ...]]:
    """Every assignment at once, in the order each account reports its labels."""
    labels: dict[tuple[str, str], list[str]] = {}

    for row in connection.execute(SELECT_LABELS_BY_ACCOUNT_SQL):
        labels.setdefault((str(row["connection_id"]), str(row["account_id"])), []).append(str(row["label"]))

    return {key: tuple(names) for key, names in labels.items()}


def get_label_case_insensitive(connection: sqlite3.Connection, name: str) -> str | None:
    row = connection.execute(SELECT_LABEL_SQL, (name,)).fetchone()

    return None if row is None else str(row["name"])


def insert_label(connection: sqlite3.Connection, name: str) -> None:
    connection.execute(INSERT_LABEL_SQL, (name,))


def insert_account_label(
    connection: sqlite3.Connection, connection_id: str, account_id: str, label: str, created_at: str
) -> None:
    connection.execute(INSERT_ACCOUNT_LABEL_SQL, (connection_id, account_id, label, created_at))


def delete_account_labels(connection: sqlite3.Connection, connection_id: str, account_id: str) -> None:
    connection.execute(DELETE_ACCOUNT_LABELS_SQL, (connection_id, account_id))


def delete_orphan_labels(connection: sqlite3.Connection) -> None:
    connection.execute(DELETE_ORPHAN_LABELS_SQL)


def upsert_account(connection: sqlite3.Connection, account: Account, fetched_at: str) -> None:
    connection.execute(
        UPSERT_ACCOUNT_SQL,
        (
            account.connection_id,
            account.account_id,
            account.connection_name,
            account.name,
            account.currency,
            account.balance_cents,
            account.available_balance_cents,
            account.balance_date,
            int(account.include_in_cash),
            fetched_at,
            fetched_at,
        ),
    )


def upsert_account_balance(connection: sqlite3.Connection, account: Account, fetched_at: str) -> None:
    connection.execute(
        UPSERT_ACCOUNT_BALANCE_SQL,
        (
            account.connection_id,
            account.account_id,
            account.balance_date,
            account.balance_cents,
            account.available_balance_cents,
            fetched_at,
        ),
    )
