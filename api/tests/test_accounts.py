"""Account metadata: the user's own name and note, and the update that writes them.

No network and no fixtures: every connection is in-memory and migrated, and the service is driven
exactly as a router drives it.
"""

import sqlite3

import pytest

from app.accounts.errors import accounts_errors as errors
from app.accounts.model.accounts_model import Account, AccountChanges
from app.accounts.service import accounts_service as service
from app.common import db, migrations
from app.common.simplefin_api import SimpleFinAccount


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrations.run_migrations(connection)

    return connection


def seed_account(
    connection: sqlite3.Connection,
    connection_id: str = "CON-1",
    account_id: str = "ACT-1",
    name: str = "Everyday Checking",
    connection_name: str = "Stub Bank",
    display_name: str | None = None,
    description: str | None = None,
    include_in_cash: bool = True,
) -> None:
    connection.execute(
        """
        INSERT INTO accounts (
            connection_id, account_id, connection_name, name, display_name, description, currency,
            balance_cents, available_balance_cents, balance_date, include_in_cash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'USD', 10000, NULL, '2026-11-10', ?, '2026-11-10T00:00:00+00:00',
                  '2026-11-10T00:00:00+00:00')
        """,
        (connection_id, account_id, connection_name, name, display_name, description, int(include_in_cash)),
    )
    connection.commit()


def stored_account(connection: sqlite3.Connection, connection_id: str = "CON-1", account_id: str = "ACT-1") -> Account:
    return next(
        account
        for account in service.list_accounts(connection)
        if (account.connection_id, account.account_id) == (connection_id, account_id)
    )


def test_a_partial_update_leaves_the_fields_it_does_not_carry_alone() -> None:
    connection = make_connection()
    seed_account(connection, display_name="Everyday", description="Spending money", include_in_cash=False)

    service.update_account(connection, "CON-1", "ACT-1", AccountChanges(description="Household spending"))

    stored = stored_account(connection)
    assert stored.description == "Household spending"
    assert stored.display_name == "Everyday"
    assert stored.include_in_cash is False
    assert stored.name == "Everyday Checking"


def test_a_blank_display_name_falls_back_to_the_fetched_one() -> None:
    connection = make_connection()
    seed_account(connection, display_name="Everyday")

    updated = service.update_account(connection, "CON-1", "ACT-1", AccountChanges(display_name="   "))

    assert updated.display_name is None
    assert updated.name == "Everyday Checking"
    assert stored_account(connection).display_name is None


def test_a_blank_description_clears_it() -> None:
    connection = make_connection()
    seed_account(connection, description="Spending money")

    updated = service.update_account(connection, "CON-1", "ACT-1", AccountChanges(description=""))

    assert updated.description is None
    assert stored_account(connection).description is None


def test_a_description_past_the_cap_is_refused() -> None:
    connection = make_connection()
    seed_account(connection)

    service.update_account(connection, "CON-1", "ACT-1", AccountChanges(description="x" * 500))

    with pytest.raises(errors.AccountDescriptionError, match="500 characters"):
        service.update_account(connection, "CON-1", "ACT-1", AccountChanges(description="x" * 501))

    assert stored_account(connection).description == "x" * 500


def test_an_update_carrying_no_fields_is_refused() -> None:
    connection = make_connection()
    seed_account(connection)

    with pytest.raises(errors.AccountUpdateError, match="needs at least one"):
        service.update_account(connection, "CON-1", "ACT-1", AccountChanges())

    assert stored_account(connection).display_name is None


def test_an_unknown_account_is_refused() -> None:
    connection = make_connection()
    seed_account(connection)

    with pytest.raises(errors.UnknownAccountError, match="Unknown account ACT-9"):
        service.update_account(connection, "CON-1", "ACT-9", AccountChanges(display_name="Everyday"))

    assert stored_account(connection).display_name is None


def test_the_cash_flag_updates_on_its_own() -> None:
    connection = make_connection()
    seed_account(connection, display_name="Everyday", include_in_cash=True)

    updated = service.update_account(connection, "CON-1", "ACT-1", AccountChanges(include_in_cash=False))

    assert updated.include_in_cash is False
    assert updated.display_name == "Everyday"


def test_accounts_are_ordered_by_connection_then_resolved_name() -> None:
    """The display name is what the list sorts by, not the name the fetch overwrites."""
    connection = make_connection()
    seed_account(
        connection, connection_id="CON-2", account_id="ACT-3", name="Aardvark Checking", connection_name="Stub Bank"
    )
    seed_account(
        connection, connection_id="CON-1", account_id="ACT-1", name="Zebra Checking", connection_name="Alpha Bank"
    )
    seed_account(
        connection,
        connection_id="CON-1",
        account_id="ACT-2",
        name="Aardvark Savings",
        connection_name="Alpha Bank",
        display_name="Zzz Savings",
    )

    assert [account.account_id for account in service.list_accounts(connection)] == ["ACT-1", "ACT-2", "ACT-3"]


def test_an_ingest_upsert_keeps_the_display_name_and_the_description() -> None:
    connection = make_connection()
    seed_account(connection, display_name="Everyday", description="Spending money")
    fetched = SimpleFinAccount.model_validate(
        {
            "id": "ACT-1",
            "name": "CHECKING XXXXX1234",
            "conn_id": "CON-1",
            "currency": "USD",
            "balance": "100.00",
            "balance-date": 1_790_000_000,
            "transactions": [],
        }
    )

    service.upsert_account(connection, fetched, "CON-1", "Stub Bank", db.now_iso())

    stored = stored_account(connection)
    assert stored.name == "CHECKING XXXXX1234"
    assert stored.display_name == "Everyday"
    assert stored.description == "Spending money"
