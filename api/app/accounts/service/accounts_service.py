"""Storing one SimpleFIN account: the connection it belongs to, and its balance row.

This is the account half of ingest. The transaction half lives in `transactions_service`,
and the fetch that drives both lives in `fetches_service`. The account endpoints live here too,
so a router only ever reads its request and answers with whatever this module returns.
"""

import sqlite3
from dataclasses import replace
from typing import Any

from app.accounts.constants.accounts_constants import DESCRIPTION_MAXIMUM_LENGTH, NON_CASH_ACCOUNT_TYPES
from app.accounts.errors.accounts_errors import AccountDescriptionError, AccountUpdateError, UnknownAccountError
from app.accounts.model.accounts_model import Account, AccountChanges
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


def list_accounts(connection: sqlite3.Connection) -> list[Account]:
    """Every stored account, ordered by connection then resolved name."""
    return persistence.get_accounts(connection)


def resolve_display_name(display_name: str) -> str | None:
    """A blank name is not a name: it hands the account back to what the institution calls it."""
    return display_name.strip() or None


def resolve_description(description: str) -> str | None:
    """A blank description is an empty one, and a note is never longer than the cap."""
    trimmed = description.strip()

    if len(trimmed) > DESCRIPTION_MAXIMUM_LENGTH:
        raise AccountDescriptionError(f"A description can be at most {DESCRIPTION_MAXIMUM_LENGTH} characters.")

    return trimmed or None


def update_account(
    connection: sqlite3.Connection, connection_id: str, account_id: str, changes: AccountChanges
) -> Account:
    """Write the fields `changes` carries and return the stored account; an unknown key is the caller's error."""
    if changes.is_empty:
        raise AccountUpdateError(
            "An account update needs at least one of a display name, a description or the cash flag."
        )

    with connection:
        stored = persistence.get_account(connection, connection_id, account_id)

        if stored is None:
            raise UnknownAccountError(f"Unknown account {account_id} on connection {connection_id}.")

        display_name = (
            stored.display_name if changes.display_name is None else resolve_display_name(changes.display_name)
        )
        description = stored.description if changes.description is None else resolve_description(changes.description)
        include_in_cash = stored.include_in_cash if changes.include_in_cash is None else changes.include_in_cash
        updated = replace(stored, display_name=display_name, description=description, include_in_cash=include_in_cash)
        persistence.update_account(connection, updated)

    return updated


def upsert_account(
    connection: sqlite3.Connection,
    account: SimpleFinAccount,
    connection_id: str,
    connection_name: str,
    fetched_at: str,
) -> None:
    """Write the account and its balance row.

    The upsert writes the fetched columns only, so a fetch can never undo a rename or a note.
    An account with no balance fails the fetch rather than being stored as zero: a zero would
    silently change the cash total and the net worth figure.
    """
    balance_cents = parse_cents(account.balance)

    if balance_cents is None:
        raise SimpleFinError(f"SimpleFin account {account.id} reported no balance.")

    stored = Account(
        connection_id=connection_id,
        account_id=account.id,
        connection_name=connection_name,
        name=account.name,
        display_name=None,
        description=None,
        currency=account.currency,
        balance_cents=balance_cents,
        available_balance_cents=parse_cents(account.available_balance),
        balance_date=local_date(account.balance_date).isoformat(),
        include_in_cash=infer_include_in_cash(account.extra),
    )

    persistence.upsert_account(connection, stored, fetched_at)
    persistence.upsert_account_balance(connection, stored, fetched_at)
