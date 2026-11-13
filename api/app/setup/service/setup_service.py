"""The connection lifecycle: claim an access URL, spend it, and report what is stored.

Every check the setup endpoints make lives here, including the quota guard, so a router only
reads its request and answers with what this module returns.
"""

import sqlite3

from app.accounts.persistence import accounts_persistence
from app.common import credentials, simplefin
from app.fetches.persistence import fetches_persistence
from app.fetches.service import fetches_service
from app.setup.errors.setup_errors import (
    AlreadyConnectedError,
    NotConnectedError,
    RefreshNotAllowedError,
)
from app.setup.model.setup_model import (
    BackfillReport,
    ConnectReport,
    RefreshReport,
    StatusReport,
)
from app.transactions.persistence import transactions_persistence


def get_status(connection: sqlite3.Connection) -> StatusReport:
    """Everything the app knows about its connection, without naming the access URL."""
    stored = credentials.read_credentials()

    return StatusReport(
        connected=stored is not None,
        credential_claimed_at=stored.claimed_at if stored is not None else None,
        account_count=accounts_persistence.count_accounts(connection),
        transaction_count=transactions_persistence.count_transactions(connection),
        last_fetch=fetches_persistence.get_last_fetch(connection),
        refresh_guard=fetches_service.refresh_guard(connection),
    )


def connect(connection: sqlite3.Connection, setup_token: str, replace: bool) -> ConnectReport:
    """Claim the token, store the access URL, and run the 12-month backfill it unlocks."""
    if credentials.read_credentials() is not None and not replace:
        raise AlreadyConnectedError("Already connected. Send replace=true to claim a new access URL.")

    source = simplefin.get_account_source()
    access_url = source.claim(setup_token)
    stored = credentials.write_credentials(access_url)
    backfill = fetches_service.run_backfill(connection, source, stored.access_url)

    return ConnectReport(
        account_count=accounts_persistence.count_accounts(connection),
        backfill_windows=len(backfill.windows),
        transactions_stored=backfill.transactions_stored,
    )


def refresh(connection: sqlite3.Connection) -> RefreshReport:
    """One five-day window, refused while the quota guard is active."""
    stored = credentials.read_credentials()

    if stored is None:
        raise NotConnectedError("No access URL is stored yet. Connect with a setup token first.")

    guard = fetches_service.refresh_guard(connection)

    if not guard.allowed:
        raise RefreshNotAllowedError(guard.next_allowed_at)

    source = simplefin.get_account_source()
    result = fetches_service.run_refresh(connection, source, stored.access_url)
    next_guard = fetches_service.refresh_guard(connection)

    return RefreshReport(
        fetched_at=result.fetched_at,
        account_count=accounts_persistence.count_accounts(connection),
        transactions_stored=result.transactions_stored,
        refresh_guard=next_guard,
    )


def backfill(connection: sqlite3.Connection, months: int) -> BackfillReport:
    """An explicit, deliberate spend, so it is not guarded."""
    stored = credentials.read_credentials()

    if stored is None:
        raise NotConnectedError("No access URL is stored yet. Connect with a setup token first.")

    source = simplefin.get_account_source()
    backfill_result = fetches_service.run_backfill(connection, source, stored.access_url, months)

    return BackfillReport(
        windows=len(backfill_result.windows),
        transactions_stored=backfill_result.transactions_stored,
    )
