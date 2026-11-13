"""Storing one SimpleFIN account: the connection it belongs to, and its balance row.

This is the account half of ingest. The transaction half lives in `transactions_service`,
and the fetch that drives both lives in `fetches_service`.
"""

import sqlite3
from typing import Any

from app.accounts.constants.accounts_constants import NON_CASH_ACCOUNT_TYPES
from app.accounts.model.accounts_model import AccountRow
from app.accounts.persistence import accounts_persistence as persistence
from app.common.dates import local_date
from app.common.errors import SimpleFinError
from app.common.money import parse_cents
from app.common.simplefin_api import SimpleFinAccount, SimpleFinConnection


def resolve_connection(account: SimpleFinAccount, connections_by_id: dict[str, SimpleFinConnection]) -> tuple[str, str]:
    """The account's connection id and display name, from the payload's own declarations."""
    if account.conn_id:
        connection = connections_by_id.get(account.conn_id)
        name = (connection.name if connection is not None else None) or account.conn_name or account.conn_id

        return account.conn_id, name

    # Protocol v1 nests the institution on the account and has no connection ids at all.
    if account.org is not None:
        identifier = account.org.sfin_url or account.org.domain

        if identifier:
            return identifier, account.org.name or identifier

    raise SimpleFinError(f"SimpleFIN account {account.id} carries no connection identifier; refusing to guess one.")


def infer_include_in_cash(extra: dict[str, Any]) -> bool:
    """Anything unknown or missing stays in the cash total, which keeps it conservative."""
    account_type = extra.get("type")
    is_non_cash = isinstance(account_type, str) and account_type.strip().lower() in NON_CASH_ACCOUNT_TYPES

    return not is_non_cash


def upsert_account(
    connection: sqlite3.Connection,
    account: SimpleFinAccount,
    connection_id: str,
    connection_name: str,
    fetched_at: str,
) -> AccountRow:
    """Write the account and its balance row, and return what was stored.

    An account with no balance fails the fetch rather than being stored as zero: a zero would
    silently change the cash total and the net worth figure.
    """
    balance_cents = parse_cents(account.balance)

    if balance_cents is None:
        raise SimpleFinError(f"SimpleFin account {account.id} reported no balance.")

    row = AccountRow(
        connection_id=connection_id,
        account_id=account.id,
        connection_name=connection_name,
        name=account.name,
        currency=account.currency,
        balance_cents=balance_cents,
        available_balance_cents=parse_cents(account.available_balance),
        balance_date=local_date(account.balance_date).isoformat(),
        include_in_cash=infer_include_in_cash(account.extra),
    )

    persistence.upsert_account_row(connection, row, fetched_at)
    persistence.upsert_account_balance_row(connection, row, fetched_at)

    return row
