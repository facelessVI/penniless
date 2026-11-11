"""Category data as tables: exact matching, validation, re-apply, and rules surviving an ingest.

No network, no fixtures, and no on-disk database: every connection is in-memory and migrated, and the
one fixture-reset test uses pytest's temporary directory.
"""

import sqlite3
from pathlib import Path

import pytest

from app import categorize, db, ingest
from app.schemas import SimpleFinAccount

DECLARED_CATEGORIES = (
    "Income",
    "Rent",
    "Utilities",
    "Groceries",
    "Dining",
    "Transport",
    "Shopping",
    "Health",
    "Subscriptions",
    "Transfers",
    "Uncategorized",
)
BALANCE_EPOCH = 1_790_000_000
POSTED_EPOCH = 1_789_000_000


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    db.run_migrations(connection)

    return connection


def seed_account(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO accounts (
            connection_id, account_id, connection_name, name, currency, balance_cents,
            available_balance_cents, balance_date, include_in_cash, created_at, updated_at
        ) VALUES ('CON-1', 'ACT-1', 'Stub Bank', 'Everyday Checking', 'USD', 10000, NULL, '2026-11-10', 1,
                  '2026-11-10T00:00:00+00:00', '2026-11-10T00:00:00+00:00')
        """
    )


def seed_rule(connection: sqlite3.Connection, description: str, category: str) -> None:
    timestamp = db.now_iso()
    connection.execute(
        "INSERT INTO rules (description, category, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (description, category, timestamp, timestamp),
    )
    connection.commit()


def seed_transaction(
    connection: sqlite3.Connection, transaction_id: str, description: str, category: str = "Uncategorized"
) -> None:
    connection.execute(
        """
        INSERT INTO transactions (
            connection_id, account_id, transaction_id, posted_at, posted_date, transacted_at,
            description, amount_cents, category, created_at, updated_at
        ) VALUES ('CON-1', 'ACT-1', ?, '2026-11-10T00:00:00+00:00', '2026-11-10', NULL, ?, -1199, ?,
                  '2026-11-10T00:00:00+00:00', '2026-11-10T00:00:00+00:00')
        """,
        (transaction_id, description, category),
    )
    connection.commit()


def stored_category(connection: sqlite3.Connection, transaction_id: str) -> str:
    row = connection.execute(
        "SELECT category FROM transactions WHERE connection_id = 'CON-1' AND account_id = 'ACT-1' "
        "AND transaction_id = ?",
        (transaction_id,),
    ).fetchone()
    assert row is not None

    return str(row["category"])


def test_seeded_categories_keep_their_declared_order() -> None:
    """The migration seeds the names and nothing else: a fresh database has no rules at all."""
    rules = categorize.load_rules(make_connection())

    assert rules.categories == DECLARED_CATEGORIES
    assert rules.rules == {}


def test_classify_is_an_exact_description_match() -> None:
    """A rule keys on the whole description, so a merchant suffix makes it a different merchant."""
    connection = make_connection()
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    rules = categorize.load_rules(connection)

    assert rules.classify("SPOTIFY USA") == "Subscriptions"
    assert rules.classify("SPOTIFY USA 877-7781161 NY") == categorize.UNCATEGORIZED_CATEGORY
    assert rules.classify("spotify usa") == categorize.UNCATEGORIZED_CATEGORY
    assert rules.classify("") == categorize.UNCATEGORIZED_CATEGORY


def test_load_rules_rejects_an_empty_category_list() -> None:
    connection = make_connection()
    connection.execute("DELETE FROM categories")

    with pytest.raises(categorize.CategoryRulesError, match="empty"):
        categorize.load_rules(connection)


def test_load_rules_rejects_a_missing_uncategorized_bucket() -> None:
    connection = make_connection()
    connection.execute("DELETE FROM categories WHERE name = 'Uncategorized'")

    with pytest.raises(categorize.CategoryRulesError, match="Uncategorized"):
        categorize.load_rules(connection)


def test_load_rules_rejects_a_rule_for_an_undeclared_category() -> None:
    """Reachable only by hand-editing the database with foreign keys off, which is what validation is for."""
    connection = make_connection()
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("UPDATE rules SET category = 'Nonsense'")

    with pytest.raises(categorize.CategoryRulesError, match="undeclared category"):
        categorize.load_rules(connection)


def test_apply_rules_relabels_every_stored_row_and_is_idempotent() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA")
    seed_transaction(connection, "TX-2", "CORNER STORE")
    seed_transaction(connection, "TX-3", "SPOTIFY USA")
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")

    result = categorize.apply_rules(connection, categorize.load_rules(connection))

    assert result.updated == 2
    assert result.uncategorized == 1
    assert stored_category(connection, "TX-1") == "Subscriptions"
    assert stored_category(connection, "TX-3") == "Subscriptions"
    assert stored_category(connection, "TX-2") == categorize.UNCATEGORIZED_CATEGORY
    assert categorize.apply_rules(connection, categorize.load_rules(connection)).updated == 0


def test_apply_rules_demotes_rows_whose_rule_is_gone() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA", "Subscriptions")

    result = categorize.apply_rules(connection, categorize.load_rules(connection))

    assert result.updated == 1
    assert stored_category(connection, "TX-1") == categorize.UNCATEGORIZED_CATEGORY


def test_a_learned_rule_survives_an_ingest_upsert() -> None:
    """The whole point of rules as data: a re-upsert must not undo a learned category."""
    connection = make_connection()
    seed_rule(connection, "STUB PURCHASE", "Dining")
    rules = categorize.load_rules(connection)
    account = SimpleFinAccount.model_validate(
        {
            "id": "ACT-1",
            "name": "Everyday Checking",
            "conn_id": "CON-1",
            "currency": "USD",
            "balance": "100.00",
            "balance-date": BALANCE_EPOCH,
            "transactions": [
                {"id": "TX-1", "posted": POSTED_EPOCH, "amount": "-12.34", "description": "STUB PURCHASE"}
            ],
        }
    )

    ingest.upsert_account(connection, account, "CON-1", "Stub Bank", db.now_iso(), rules)
    ingest.upsert_account(connection, account, "CON-1", "Stub Bank", db.now_iso(), rules)

    assert ingest.count_rows(connection, "transactions") == 1
    assert stored_category(connection, "TX-1") == "Dining"


def test_fixture_reset_keeps_learned_rules(tmp_path: Path) -> None:
    """The dev loop keeps what it learned: the file is rebuilt, the rules come back with it."""
    database_path = tmp_path / "penniless-dev.sqlite"
    connection = db.connect(database_path)
    db.run_migrations(connection)
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    connection.close()

    snapshot = db.read_rules_snapshot(database_path)

    assert snapshot == [("SPOTIFY USA", "Subscriptions")]

    db.reset_database(database_path)

    assert not database_path.exists()

    connection = db.connect(database_path)
    db.run_migrations(connection)

    assert db.restore_rules(connection, snapshot) == 1
    assert categorize.load_rules(connection).rules == {"SPOTIFY USA": "Subscriptions"}
    connection.close()


def test_read_rules_snapshot_tolerates_a_missing_database(tmp_path: Path) -> None:
    assert db.read_rules_snapshot(tmp_path / "absent.sqlite") == []
