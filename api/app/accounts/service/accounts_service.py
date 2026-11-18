"""Storing one SimpleFIN account: the connection it belongs to, and its balance row.

This is the account half of ingest. The transaction half lives in `transactions_service`,
and the fetch that drives both lives in `fetches_service`. The account endpoints live here too,
so a router only ever reads its request and answers with whatever this module returns.

A cash account is the other writer: the user creates it, names it and sets its balance, and no fetch
ever names its key. `source` is what tells the two apart, and it is written once.
"""

import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from typing import Any

from app.accounts.constants.accounts_constants import (
    DESCRIPTION_MAXIMUM_LENGTH,
    LABEL_NAME_RULE,
    MANUAL_CONNECTION_ID,
    MANUAL_CONNECTION_NAME,
    MANUAL_CURRENCY,
    MANUAL_SOURCE,
    NON_CASH_ACCOUNT_TYPES,
    SIMPLEFIN_SOURCE,
)
from app.accounts.errors.accounts_errors import (
    AccountDescriptionError,
    AccountNameError,
    AccountUpdateError,
    LabelNameError,
    ManualAccountError,
    UnknownAccountError,
)
from app.accounts.model.accounts_model import Account, AccountChanges
from app.accounts.persistence import accounts_persistence as persistence
from app.common import db
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
    """Every stored account, ordered by connection then resolved name, each with its own labels."""
    labels_by_account = persistence.get_labels_by_account(connection)

    return [
        replace(account, labels=labels_by_account.get((account.connection_id, account.account_id), ()))
        for account in persistence.get_accounts(connection)
    ]


def replace_labels(connection: sqlite3.Connection, account: Account, labels: Sequence[str]) -> tuple[str, ...]:
    """Write `labels` as the account's complete set: create unknown names and prune labels nobody carries.

    A known name keeps the spelling already stored, so one vocabulary never grows two casings of the
    same grouping. Every name is validated before the first write, and the service's transaction holds
    the replacement, so a refused set leaves the account as it was.
    """
    normalized = [LABEL_NAME_RULE.normalize(label) for label in labels]
    seen: set[str] = set()

    for label in normalized:
        if label.casefold() in seen:
            raise LabelNameError(f"The label {label!r} is attached twice.")

        seen.add(label.casefold())

    resolved = []

    for label in normalized:
        stored = persistence.get_label_case_insensitive(connection, label)
        resolved.append(label if stored is None else stored)

    created_at = db.now_iso()
    persistence.delete_account_labels(connection, account.connection_id, account.account_id)

    for label in resolved:
        persistence.insert_label(connection, label)
        persistence.insert_account_label(connection, account.connection_id, account.account_id, label, created_at)

    persistence.delete_orphan_labels(connection)

    return persistence.get_account_labels(connection, account.connection_id, account.account_id)


def resolve_display_name(display_name: str) -> str | None:
    """A blank name is not a name: it hands the account back to what the institution calls it."""
    return display_name.strip() or None


def resolve_account_name(name: str) -> str:
    """A cash account has no institution name to fall back to, so a blank one is refused, not blanked."""
    trimmed = name.strip()

    if not trimmed:
        raise AccountNameError("A cash account needs a name.")

    return trimmed


def ensure_balance_is_editable(account: Account) -> None:
    if account.source != MANUAL_SOURCE:
        raise ManualAccountError(
            "Only a cash account's balance can be edited, because a fetch writes every other account's balance."
        )


def ensure_account_is_deletable(account: Account) -> None:
    if account.source != MANUAL_SOURCE:
        raise ManualAccountError(
            "Only a cash account can be deleted; a fetched account comes back with the next fetch."
        )


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
            "An account update needs at least one of a display name, a description, a label set, the cash "
            "flag or a balance."
        )

    with connection:
        stored = persistence.get_account(connection, connection_id, account_id)

        if stored is None:
            raise UnknownAccountError(f"Unknown account {account_id} on connection {connection_id}.")

        if changes.balance_cents is not None:
            ensure_balance_is_editable(stored)

        display_name = (
            stored.display_name if changes.display_name is None else resolve_display_name(changes.display_name)
        )
        description = stored.description if changes.description is None else resolve_description(changes.description)
        include_in_cash = stored.include_in_cash if changes.include_in_cash is None else changes.include_in_cash
        labels = stored.labels if changes.labels is None else replace_labels(connection, stored, changes.labels)
        # A cash balance is the user's own number rather than a reported one, so setting it dates it today.
        balance_cents = stored.balance_cents if changes.balance_cents is None else changes.balance_cents
        balance_date = stored.balance_date if changes.balance_cents is None else date.today().isoformat()
        updated = replace(
            stored,
            display_name=display_name,
            description=description,
            include_in_cash=include_in_cash,
            labels=labels,
            balance_cents=balance_cents,
            balance_date=balance_date,
        )
        persistence.update_account(connection, updated)

    return updated


def create_manual_account(
    connection: sqlite3.Connection,
    name: str,
    balance_cents: int,
    description: str | None,
    labels: Sequence[str],
) -> Account:
    """Store a cash account the user created; every field is validated before the first write."""
    created = Account(
        connection_id=MANUAL_CONNECTION_ID,
        account_id=str(uuid.uuid4()),
        connection_name=MANUAL_CONNECTION_NAME,
        name=resolve_account_name(name),
        display_name=None,
        description=None if description is None else resolve_description(description),
        currency=MANUAL_CURRENCY,
        balance_cents=balance_cents,
        available_balance_cents=None,
        balance_date=date.today().isoformat(),
        include_in_cash=True,
        source=MANUAL_SOURCE,
    )

    with connection:
        persistence.insert_account(connection, created)
        attached = replace_labels(connection, created, labels)

    return replace(created, labels=attached)


def delete_account(connection: sqlite3.Connection, connection_id: str, account_id: str) -> list[Account]:
    """Drop a cash account, prune the labels only it carried, and answer with the accounts left."""
    with connection:
        stored = persistence.get_account(connection, connection_id, account_id)

        if stored is None:
            raise UnknownAccountError(f"Unknown account {account_id} on connection {connection_id}.")

        ensure_account_is_deletable(stored)
        persistence.delete_account(connection, connection_id, account_id)
        persistence.delete_orphan_labels(connection)

    return list_accounts(connection)


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
        source=SIMPLEFIN_SOURCE,
    )

    persistence.upsert_account(connection, stored, fetched_at)
    persistence.upsert_account_balance(connection, stored, fetched_at)
