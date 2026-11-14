"""Rules as patterns: precedence, matching, validation, re-apply, and the rules table's lifecycle.

No network, no fixtures, and no on-disk database except in the snapshot tests: every connection is
in-memory and migrated, and the tests that need a database from before migration 004 live in a
pytest temporary directory.
"""

import sqlite3
from pathlib import Path

import pytest

from app.accounts.service import accounts_service
from app.categories.constants import categories_constants as constants
from app.categories.errors import categories_errors as errors
from app.categories.model import categories_model as models
from app.categories.service import categories_service as service
from app.common import db, migrations
from app.common.config import MIGRATIONS_DIR
from app.common.simplefin_api import SimpleFinAccount
from app.transactions.persistence import transactions_persistence
from app.transactions.service import transactions_service

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
BEFORE_PATTERNS_MIGRATION = "003_unique_category_name.sql"
PATTERNS_MIGRATION = "004_rule_patterns.sql"


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrations.run_migrations(connection)

    return connection


def apply_migrations_up_to(connection: sqlite3.Connection, last_filename: str) -> None:
    """Stop after `last_filename`, so a test can seed the schema a migration is written against."""
    connection.executescript(migrations.MIGRATIONS_TABLE_DDL)

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name > last_filename:
            break

        migrations.apply_migration(connection, path)


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


def seed_rule(
    connection: sqlite3.Connection,
    pattern: str,
    category: str,
    match_type: str = constants.MATCH_TYPE_EXACT,
    updated_at: str | None = None,
) -> None:
    timestamp = updated_at or db.now_iso()
    connection.execute(
        "INSERT INTO rules (match_type, pattern, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (match_type, pattern, category, timestamp, timestamp),
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


def store_account(
    connection: sqlite3.Connection,
    account: SimpleFinAccount,
    connection_id: str,
    rules: models.CategoryRules,
    connection_name: str = "Stub Bank",
) -> None:
    """Write one account the way an ingest does: the account row, then its transactions."""
    fetched_at = db.now_iso()
    accounts_service.upsert_account(connection, account, connection_id, connection_name, fetched_at)
    transactions_service.upsert_transactions(connection, account, connection_id, fetched_at, rules)


def stored_category(connection: sqlite3.Connection, transaction_id: str) -> str:
    row = connection.execute(
        "SELECT category FROM transactions WHERE connection_id = 'CON-1' AND account_id = 'ACT-1' "
        "AND transaction_id = ?",
        (transaction_id,),
    ).fetchone()
    assert row is not None

    return str(row["category"])


def rule_pairs(connection: sqlite3.Connection) -> list[tuple[str, str, str]]:
    return [
        (str(row[0]), str(row[1]), str(row[2]))
        for row in connection.execute("SELECT match_type, pattern, category FROM rules ORDER BY match_type, pattern")
    ]


def rule_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT count(*) FROM rules").fetchone()[0])


def test_seeded_categories_keep_their_declared_order() -> None:
    """The migration seeds the names and nothing else: a fresh database has no rules at all."""
    rules = service.get_category_rules(make_connection())

    assert rules.categories == DECLARED_CATEGORIES
    assert rules.rules == ()


def test_an_exact_rule_matches_the_whole_description_only() -> None:
    """`exact` stays case-sensitive: a merchant suffix or a different case is a different merchant."""
    connection = make_connection()
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    rules = service.get_category_rules(connection)

    assert rules.classify("SPOTIFY USA") == "Subscriptions"
    assert rules.classify("SPOTIFY USA 877-7781161 NY") == constants.UNCATEGORIZED_CATEGORY
    assert rules.classify("spotify usa") == constants.UNCATEGORIZED_CATEGORY
    assert rules.classify("") == constants.UNCATEGORIZED_CATEGORY


def test_a_contains_rule_matches_a_case_insensitive_substring() -> None:
    connection = make_connection()
    seed_rule(connection, "spotify usa", "Subscriptions", match_type=constants.MATCH_TYPE_CONTAINS)
    rules = service.get_category_rules(connection)

    assert rules.classify("SPOTIFY USA") == "Subscriptions"
    assert rules.classify("SPOTIFY USA 877-7781161 NY") == "Subscriptions"
    assert rules.classify("MY SPOTIFY USA") == "Subscriptions"
    # The pattern is longer than the description, so it is not a substring of it.
    assert rules.classify("SPOTIFY") == constants.UNCATEGORIZED_CATEGORY


def test_a_contains_rule_treats_wildcard_characters_as_literal_text() -> None:
    """Matching is a literal substring, never a SQL or regex pattern: `_` and `%` are characters."""
    connection = make_connection()
    seed_rule(connection, "A_C", "Groceries", match_type=constants.MATCH_TYPE_CONTAINS)
    seed_rule(connection, "50% OFF", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS)
    rules = service.get_category_rules(connection)

    assert rules.classify("PURCHASE A_C 001") == "Groceries"
    assert rules.classify("ABC") == constants.UNCATEGORIZED_CATEGORY
    assert rules.classify("50% OFF TODAY") == "Shopping"
    assert rules.classify("5000 OFF") == constants.UNCATEGORIZED_CATEGORY


def test_an_exact_rule_beats_a_contains_rule_for_the_same_text() -> None:
    """The tie that length alone cannot break: the same word as a whole description and as a keyword."""
    connection = make_connection()
    seed_rule(connection, "AMAZON", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS)
    seed_rule(connection, "AMAZON", "Dining")
    rules = service.get_category_rules(connection)

    assert rules.classify("AMAZON") == "Dining"
    assert rules.classify("AMAZON MKTPLACE PMTS") == "Shopping"


def test_a_longer_contains_pattern_wins() -> None:
    connection = make_connection()
    seed_rule(connection, "AMAZON", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS)
    seed_rule(connection, "AMAZON PRIME", "Subscriptions", match_type=constants.MATCH_TYPE_CONTAINS)
    rules = service.get_category_rules(connection)

    assert rules.classify("AMAZON PRIME*2X") == "Subscriptions"
    assert rules.classify("AMAZON MKTPLACE PMTS") == "Shopping"


def test_equally_long_contains_patterns_resolve_to_the_newest_rule() -> None:
    connection = make_connection()
    seed_rule(
        connection,
        "SHOP A",
        "Shopping",
        match_type=constants.MATCH_TYPE_CONTAINS,
        updated_at="2026-11-01T00:00:00+00:00",
    )
    seed_rule(
        connection,
        "SHOP B",
        "Dining",
        match_type=constants.MATCH_TYPE_CONTAINS,
        updated_at="2026-11-02T00:00:00+00:00",
    )
    rules = service.get_category_rules(connection)

    assert rules.classify("SHOP A SHOP B") == "Dining"


def test_equally_specific_rules_fall_back_to_alphabetical_order() -> None:
    """The last tiebreak has to be deterministic, or classification depends on insertion order."""
    connection = make_connection()
    timestamp = "2026-11-01T00:00:00+00:00"
    seed_rule(connection, "BB", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS, updated_at=timestamp)
    seed_rule(connection, "AA", "Dining", match_type=constants.MATCH_TYPE_CONTAINS, updated_at=timestamp)
    rules = service.get_category_rules(connection)

    assert rules.classify("AA BB") == "Dining"


def test_get_category_rules_rejects_an_empty_category_list() -> None:
    connection = make_connection()
    connection.execute("DELETE FROM categories")

    with pytest.raises(errors.CategoryRulesError, match="empty"):
        service.get_category_rules(connection)


def test_get_category_rules_rejects_a_missing_uncategorized_bucket() -> None:
    connection = make_connection()
    connection.execute("DELETE FROM categories WHERE name = 'Uncategorized'")

    with pytest.raises(errors.CategoryRulesError, match="Uncategorized"):
        service.get_category_rules(connection)


def test_get_category_rules_rejects_a_rule_for_an_undeclared_category() -> None:
    """Reachable only by hand-editing the database with foreign keys off, which is what validation is for."""
    connection = make_connection()
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("UPDATE rules SET category = 'Nonsense'")

    with pytest.raises(errors.CategoryRulesError, match="undeclared category"):
        service.get_category_rules(connection)


def test_get_category_rules_rejects_an_unknown_match_type() -> None:
    """The CHECK constraint is the first line; validation also has to refuse a hand-edited row."""
    connection = make_connection()
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    connection.execute("PRAGMA ignore_check_constraints = ON")
    connection.execute("UPDATE rules SET match_type = 'regex'")

    with pytest.raises(errors.CategoryRulesError, match="match type"):
        service.get_category_rules(connection)


def test_get_category_rules_rejects_a_blank_pattern() -> None:
    connection = make_connection()
    seed_rule(connection, "   ", "Subscriptions")

    with pytest.raises(errors.CategoryRulesError, match="empty pattern"):
        service.get_category_rules(connection)


def test_a_rule_is_unique_per_match_type_case_insensitively() -> None:
    """Two keywords that differ only in case would be two identical options; the index refuses them."""
    connection = make_connection()
    seed_rule(connection, "AMAZON", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS)

    with pytest.raises(sqlite3.IntegrityError):
        seed_rule(connection, "amazon", "Dining", match_type=constants.MATCH_TYPE_CONTAINS)

    # The same text may exist once per type: an exact rule and a keyword rule.
    seed_rule(connection, "AMAZON", "Dining")
    assert rule_count(connection) == 2


def test_apply_rules_relabels_every_stored_row_and_is_idempotent() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA")
    seed_transaction(connection, "TX-2", "CORNER STORE")
    seed_transaction(connection, "TX-3", "SPOTIFY USA")
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")

    result = service.apply_rules(connection, service.get_category_rules(connection))

    assert result.updated == 2
    assert result.uncategorized == 1
    assert stored_category(connection, "TX-1") == "Subscriptions"
    assert stored_category(connection, "TX-3") == "Subscriptions"
    assert stored_category(connection, "TX-2") == constants.UNCATEGORIZED_CATEGORY
    assert service.apply_rules(connection, service.get_category_rules(connection)).updated == 0


def test_apply_rules_uses_the_most_specific_rule_per_row() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")
    seed_transaction(connection, "TX-2", "AMAZON PRIME*2X")
    seed_rule(connection, "AMAZON", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS)
    seed_rule(connection, "AMAZON PRIME", "Subscriptions", match_type=constants.MATCH_TYPE_CONTAINS)

    service.apply_rules(connection, service.get_category_rules(connection))

    assert stored_category(connection, "TX-1") == "Shopping"
    assert stored_category(connection, "TX-2") == "Subscriptions"


def test_apply_rules_demotes_rows_whose_rule_is_gone() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA", "Subscriptions")

    result = service.apply_rules(connection, service.get_category_rules(connection))

    assert result.updated == 1
    assert stored_category(connection, "TX-1") == constants.UNCATEGORIZED_CATEGORY


def test_a_learned_rule_survives_an_ingest_upsert() -> None:
    """The whole point of rules as data: a re-upsert must not undo a learned category."""
    connection = make_connection()
    seed_rule(connection, "STUB PURCHASE", "Dining")
    rules = service.get_category_rules(connection)
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

    store_account(connection, account, "CON-1", rules)
    store_account(connection, account, "CON-1", rules)

    assert transactions_persistence.count_transactions(connection) == 1
    assert stored_category(connection, "TX-1") == "Dining"


def test_a_keyword_rule_classifies_a_transaction_it_has_never_seen() -> None:
    """Ingest classifies at write time, so a new description that contains the keyword arrives set."""
    connection = make_connection()
    seed_rule(connection, "STUB", "Dining", match_type=constants.MATCH_TYPE_CONTAINS)
    rules = service.get_category_rules(connection)
    account = SimpleFinAccount.model_validate(
        {
            "id": "ACT-1",
            "name": "Everyday Checking",
            "conn_id": "CON-1",
            "currency": "USD",
            "balance": "100.00",
            "balance-date": BALANCE_EPOCH,
            "transactions": [
                {"id": "TX-1", "posted": POSTED_EPOCH, "amount": "-12.34", "description": "STUB PURCHASE 0042"}
            ],
        }
    )

    store_account(connection, account, "CON-1", rules)

    assert stored_category(connection, "TX-1") == "Dining"


def test_fixture_reset_keeps_learned_rules(tmp_path: Path) -> None:
    """The dev loop keeps what it learned, patterns and match types included."""
    database_path = tmp_path / "penniless-dev.sqlite"
    connection = db.connect(database_path)
    migrations.run_migrations(connection)
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    seed_rule(connection, "AMAZON", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS)
    connection.close()

    snapshot = db.read_rules_snapshot(database_path)

    assert snapshot == [
        ("contains", "AMAZON", "Shopping"),
        ("exact", "SPOTIFY USA", "Subscriptions"),
    ]

    migrations.reset_database(database_path)

    assert not database_path.exists()

    connection = db.connect(database_path)
    migrations.run_migrations(connection)

    assert db.restore_rules(connection, snapshot) == 2
    assert rule_pairs(connection) == [
        ("contains", "AMAZON", "Shopping"),
        ("exact", "SPOTIFY USA", "Subscriptions"),
    ]
    connection.close()


def test_read_rules_snapshot_tolerates_a_missing_database(tmp_path: Path) -> None:
    assert db.read_rules_snapshot(tmp_path / "absent.sqlite") == []


def test_a_snapshot_from_a_database_without_match_type_restores_exact_rules(tmp_path: Path) -> None:
    """A dev database from before migration 004 still keeps what it learned across a reset."""
    database_path = tmp_path / "penniless-dev.sqlite"
    connection = db.connect(database_path)
    apply_migrations_up_to(connection, BEFORE_PATTERNS_MIGRATION)
    timestamp = db.now_iso()
    connection.execute(
        "INSERT INTO rules (description, category, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("SPOTIFY USA", "Subscriptions", timestamp, timestamp),
    )
    connection.commit()
    connection.close()

    snapshot = db.read_rules_snapshot(database_path)

    assert snapshot == [("exact", "SPOTIFY USA", "Subscriptions")]

    migrations.reset_database(database_path)

    connection = db.connect(database_path)
    migrations.run_migrations(connection)

    assert db.restore_rules(connection, snapshot) == 1
    assert rule_pairs(connection) == [("exact", "SPOTIFY USA", "Subscriptions")]
    connection.close()


def test_migration_004_turns_every_rule_into_an_exact_rule() -> None:
    """The backfill is one-to-one: nothing learned changes behaviour and nothing widens."""
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations_up_to(connection, BEFORE_PATTERNS_MIGRATION)
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA", "Subscriptions")
    timestamp = "2026-11-01T00:00:00+00:00"

    connection.execute(
        "INSERT INTO rules (description, category, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("SPOTIFY USA", "Subscriptions", timestamp, timestamp),
    )
    connection.execute(
        "INSERT INTO rules (description, category, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("CORNER STORE", "Groceries", timestamp, timestamp),
    )
    connection.commit()

    migrations.apply_migration(connection, MIGRATIONS_DIR / PATTERNS_MIGRATION)

    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info('rules')")}
    keys = {str(row[1]) for row in connection.execute("PRAGMA table_info('rules')") if row[5]}

    assert {"match_type", "pattern", "category", "created_at", "updated_at"} == columns
    assert keys == {"match_type", "pattern"}
    assert rule_pairs(connection) == [
        ("exact", "CORNER STORE", "Groceries"),
        ("exact", "SPOTIFY USA", "Subscriptions"),
    ]
    assert connection.execute("SELECT created_at FROM rules WHERE pattern = 'SPOTIFY USA'").fetchone()[0] == timestamp

    foreign_keys = {
        (str(row[2]), str(row[5]), str(row[6])) for row in connection.execute("PRAGMA foreign_key_list('rules')")
    }

    assert foreign_keys == {("categories", "CASCADE", "RESTRICT")}

    # AC3: behaviour after the migration is exactly what it was before it.
    assert service.get_category_rules(connection).classify("SPOTIFY USA") == "Subscriptions"
    assert service.get_category_rules(connection).classify("SPOTIFY USA 877-7781161 NY") == (
        constants.UNCATEGORIZED_CATEGORY
    )
    assert service.apply_rules(connection, service.get_category_rules(connection)).updated == 0


def test_migration_004_keeps_one_of_two_rules_that_differ_only_in_case() -> None:
    """The pre-004 key was case-sensitive; the new case-insensitive index needs one row, not two."""
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations_up_to(connection, BEFORE_PATTERNS_MIGRATION)
    timestamp = db.now_iso()

    connection.execute(
        "INSERT INTO rules (description, category, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("AMAZON", "Shopping", timestamp, timestamp),
    )
    connection.execute(
        "INSERT INTO rules (description, category, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("amazon", "Dining", timestamp, timestamp),
    )
    connection.commit()

    migrations.apply_migration(connection, MIGRATIONS_DIR / PATTERNS_MIGRATION)

    assert rule_pairs(connection) == [("exact", "amazon", "Dining")]


def assign(
    connection: sqlite3.Connection,
    transaction_id: str,
    category: str,
    pattern: str,
    match_type: str = constants.MATCH_TYPE_EXACT,
) -> models.AssignResult:
    return service.assign_category(connection, "CON-1", "ACT-1", transaction_id, category, match_type, pattern)


def keyword_options(connection: sqlite3.Connection, transaction_id: str = "TX-1") -> models.KeywordOptions:
    return service.list_keyword_options(connection, "CON-1", "ACT-1", transaction_id)


def test_assign_category_writes_one_rule_and_relabels_every_matching_row() -> None:
    """One merchant, one rule: every stored row with that description moves together."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA")
    seed_transaction(connection, "TX-2", "SPOTIFY USA")
    seed_transaction(connection, "TX-3", "CORNER STORE")

    result = assign(connection, "TX-1", "Subscriptions", "SPOTIFY USA")

    assert result.description == "SPOTIFY USA"
    assert result.match_type == constants.MATCH_TYPE_EXACT
    assert result.pattern == "SPOTIFY USA"
    assert result.category == "Subscriptions"
    assert result.matched == 2
    assert result.updated == 2
    assert not result.rule_deleted
    assert stored_category(connection, "TX-1") == "Subscriptions"
    assert stored_category(connection, "TX-2") == "Subscriptions"
    assert stored_category(connection, "TX-3") == constants.UNCATEGORIZED_CATEGORY
    assert rule_pairs(connection) == [("exact", "SPOTIFY USA", "Subscriptions")]


def test_assigning_a_second_category_moves_the_same_rule() -> None:
    """Re-picking a merchant corrects the rule instead of stacking a second one."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA")
    seed_transaction(connection, "TX-2", "SPOTIFY USA")
    assign(connection, "TX-1", "Subscriptions", "SPOTIFY USA")

    result = assign(connection, "TX-2", "Dining", "SPOTIFY USA")

    assert result.updated == 2
    assert rule_count(connection) == 1
    assert rule_pairs(connection) == [("exact", "SPOTIFY USA", "Dining")]
    assert stored_category(connection, "TX-1") == "Dining"


def test_assigning_a_keyword_relabels_every_matching_row() -> None:
    """The keyword reaches rows the clicked description never matched, which is the point."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")
    seed_transaction(connection, "TX-2", "AMAZON PRIME*2X")
    seed_transaction(connection, "TX-3", "CORNER STORE")

    result = assign(connection, "TX-1", "Shopping", "AMAZON", constants.MATCH_TYPE_CONTAINS)

    assert result.match_type == constants.MATCH_TYPE_CONTAINS
    assert result.pattern == "AMAZON"
    assert result.matched == 2
    assert result.updated == 2
    assert stored_category(connection, "TX-1") == "Shopping"
    assert stored_category(connection, "TX-2") == "Shopping"
    assert stored_category(connection, "TX-3") == constants.UNCATEGORIZED_CATEGORY
    assert rule_pairs(connection) == [("contains", "AMAZON", "Shopping")]


def test_assigning_a_keyword_stays_behind_a_more_specific_rule() -> None:
    """Writing a keyword does not flatten the rules that are more specific than it."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON PRIME*2X", "Subscriptions")
    seed_transaction(connection, "TX-2", "AMAZON MKTPLACE PMTS")
    seed_rule(connection, "AMAZON PRIME", "Subscriptions", match_type=constants.MATCH_TYPE_CONTAINS)

    result = assign(connection, "TX-2", "Shopping", "AMAZON", constants.MATCH_TYPE_CONTAINS)

    assert result.matched == 2
    assert result.updated == 1
    assert stored_category(connection, "TX-1") == "Subscriptions"
    assert stored_category(connection, "TX-2") == "Shopping"


def test_repointing_a_keyword_changes_one_rule_and_keeps_its_created_at() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")
    seed_transaction(connection, "TX-2", "AMAZON PRIME*2X")
    assign(connection, "TX-1", "Shopping", "AMAZON", constants.MATCH_TYPE_CONTAINS)
    created_at = connection.execute("SELECT created_at FROM rules").fetchone()[0]

    result = assign(connection, "TX-2", "Dining", "AMAZON", constants.MATCH_TYPE_CONTAINS)

    assert result.updated == 2
    assert rule_count(connection) == 1
    assert rule_pairs(connection) == [("contains", "AMAZON", "Dining")]
    assert connection.execute("SELECT created_at FROM rules").fetchone()[0] == created_at
    assert stored_category(connection, "TX-1") == "Dining"


def test_repointing_a_keyword_updates_the_rule_that_differs_only_in_case() -> None:
    """The table is case-insensitively unique per type, so a different case corrects the same rule."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")
    assign(connection, "TX-1", "Shopping", "AMAZON", constants.MATCH_TYPE_CONTAINS)

    result = assign(connection, "TX-1", "Dining", "amazon", constants.MATCH_TYPE_CONTAINS)

    assert result.pattern == "AMAZON"
    assert rule_count(connection) == 1
    assert rule_pairs(connection) == [("contains", "AMAZON", "Dining")]


def test_removing_a_keyword_deletes_its_rule_and_demotes_its_rows() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS", "Shopping")
    seed_transaction(connection, "TX-2", "AMAZON PRIME*2X", "Shopping")
    seed_rule(connection, "AMAZON", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS)

    result = assign(connection, "TX-1", constants.UNCATEGORIZED_CATEGORY, "AMAZON", constants.MATCH_TYPE_CONTAINS)

    assert result.rule_deleted
    assert result.matched == 2
    assert result.updated == 2
    assert rule_count(connection) == 0
    assert stored_category(connection, "TX-1") == constants.UNCATEGORIZED_CATEGORY
    assert stored_category(connection, "TX-2") == constants.UNCATEGORIZED_CATEGORY


def test_removing_a_keyword_leaves_its_rows_with_the_next_matching_rule() -> None:
    """Falling back is a re-classify, not a demotion to `Uncategorized` by hand."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS", "Shopping")
    seed_transaction(connection, "TX-2", "AMAZON PRIME*2X", "Subscriptions")
    seed_rule(connection, "AMAZON", "Shopping", match_type=constants.MATCH_TYPE_CONTAINS)
    seed_rule(connection, "AMAZON PRIME", "Subscriptions", match_type=constants.MATCH_TYPE_CONTAINS)

    result = assign(connection, "TX-1", constants.UNCATEGORIZED_CATEGORY, "AMAZON", constants.MATCH_TYPE_CONTAINS)

    assert result.updated == 1
    assert stored_category(connection, "TX-1") == constants.UNCATEGORIZED_CATEGORY
    assert stored_category(connection, "TX-2") == "Subscriptions"
    assert rule_pairs(connection) == [("contains", "AMAZON PRIME", "Subscriptions")]


def test_removing_a_keyword_that_has_no_rule_fails_and_writes_nothing() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")
    assign(connection, "TX-1", "Shopping", "AMAZON MKTPLACE PMTS")

    with pytest.raises(errors.UnknownRuleError, match="no contains rule for 'AMAZON'"):
        assign(connection, "TX-1", constants.UNCATEGORIZED_CATEGORY, "AMAZON", constants.MATCH_TYPE_CONTAINS)

    assert rule_pairs(connection) == [("exact", "AMAZON MKTPLACE PMTS", "Shopping")]
    assert stored_category(connection, "TX-1") == "Shopping"


def test_assign_category_rejects_a_keyword_that_is_not_in_the_description() -> None:
    """A client cannot widen a rule to a description the user was never shown."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")

    with pytest.raises(errors.RulePatternError, match="does not occur in the description"):
        assign(connection, "TX-1", "Shopping", "SPOTIFY", constants.MATCH_TYPE_CONTAINS)

    assert rule_count(connection) == 0


def test_assign_category_rejects_an_exact_pattern_that_is_not_the_description() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")

    with pytest.raises(errors.RulePatternError, match="does not occur in the description"):
        assign(connection, "TX-1", "Shopping", "AMAZON")

    assert rule_count(connection) == 0


@pytest.mark.parametrize(
    ("pattern", "match_type"),
    [("", constants.MATCH_TYPE_CONTAINS), ("   ", constants.MATCH_TYPE_EXACT)],
)
def test_assign_category_rejects_a_blank_keyword(pattern: str, match_type: str) -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")

    with pytest.raises(errors.RulePatternError, match="cannot be blank"):
        assign(connection, "TX-1", "Shopping", pattern, match_type)

    assert rule_count(connection) == 0


def test_assign_category_rejects_an_unknown_match_type() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")

    with pytest.raises(errors.RulePatternError, match="not a known match type"):
        assign(connection, "TX-1", "Shopping", "AMAZON", "regex")

    assert rule_count(connection) == 0


def test_assign_category_rejects_an_unknown_category_and_writes_nothing() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA")

    with pytest.raises(errors.CategoryRulesError, match="not a declared category"):
        assign(connection, "TX-1", "Crypto", "SPOTIFY USA")

    assert rule_count(connection) == 0
    assert stored_category(connection, "TX-1") == constants.UNCATEGORIZED_CATEGORY


def test_assign_category_rejects_an_unknown_transaction_and_writes_nothing() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA")

    with pytest.raises(errors.UnknownTransactionError, match="Unknown transaction TX-9"):
        assign(connection, "TX-9", "Subscriptions", "SPOTIFY USA")

    assert rule_count(connection) == 0
    assert stored_category(connection, "TX-1") == constants.UNCATEGORIZED_CATEGORY


def test_keyword_options_offer_the_description_its_words_and_its_phrases() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS 2026")

    options = keyword_options(connection)
    offered = [(option.match_type, option.pattern, option.source) for option in options.options]

    assert options.description == "AMAZON MKTPLACE PMTS 2026"
    assert options.effective_rule is None
    assert offered == [
        ("exact", "AMAZON MKTPLACE PMTS 2026", constants.KEYWORD_SOURCE_DESCRIPTION),
        ("contains", "AMAZON", constants.KEYWORD_SOURCE_TOKEN),
        ("contains", "MKTPLACE", constants.KEYWORD_SOURCE_TOKEN),
        ("contains", "AMAZON MKTPLACE", constants.KEYWORD_SOURCE_PHRASE),
    ]
    assert [option.matched for option in options.options] == [1, 1, 1, 1]
    assert {option.category for option in options.options} == {None}


def test_keyword_options_only_offer_phrases_that_occur_in_the_description() -> None:
    """Phrases come from neighbouring words, not from the sorted list, so none is a phantom."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "CITY POWER & LIGHT")

    phrases = [
        option for option in keyword_options(connection).options if option.source == constants.KEYWORD_SOURCE_PHRASE
    ]

    assert [option.pattern for option in phrases] == ["CITY POWER"]
    assert all(option.matched == 1 for option in phrases)


def test_keyword_options_drop_digits_short_words_and_noise() -> None:
    """`#0218`, `NC` and `POS` are not merchants; offering them just makes the select longer."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "POS DEBIT HARRIS TEETER #0218 CHARLOTTE NC")

    patterns = [option.pattern for option in keyword_options(connection).options]

    assert "0218" not in patterns
    assert "#0218" not in patterns
    assert "NC" not in patterns
    assert "POS" not in patterns
    assert "DEBIT" not in patterns
    assert patterns[1:3] == ["CHARLOTTE", "HARRIS"]


def test_keyword_options_mark_existing_rules_and_fold_the_exact_rule_into_the_description() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA")
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    seed_rule(connection, "SPOTIFY", "Dining", match_type=constants.MATCH_TYPE_CONTAINS)

    options = keyword_options(connection)
    by_pattern = {(option.match_type, option.pattern): option for option in options.options}

    assert options.effective_rule is not None
    assert (options.effective_rule.match_type, options.effective_rule.pattern) == ("exact", "SPOTIFY USA")
    assert by_pattern[("exact", "SPOTIFY USA")].category == "Subscriptions"
    assert by_pattern[("exact", "SPOTIFY USA")].source == constants.KEYWORD_SOURCE_DESCRIPTION
    assert by_pattern[("contains", "SPOTIFY")].category == "Dining"
    assert by_pattern[("contains", "SPOTIFY")].source == constants.KEYWORD_SOURCE_RULE
    # The token and the rule share one option, and the rule's category is the one that survives.
    assert [option.pattern for option in options.options].count("SPOTIFY") == 1


def test_keyword_options_include_an_existing_rule_that_is_not_a_whole_word() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA 877-7781161 NY")
    seed_rule(connection, "USA 877", "Subscriptions", match_type=constants.MATCH_TYPE_CONTAINS)

    options = keyword_options(connection)
    by_pattern = {(option.match_type, option.pattern): option for option in options.options}

    assert by_pattern[("contains", "USA 877")].source == constants.KEYWORD_SOURCE_RULE
    assert by_pattern[("contains", "USA 877")].category == "Subscriptions"
    assert by_pattern[("contains", "USA 877")].matched == 1


def test_keyword_options_count_the_rows_each_candidate_would_match() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "AMAZON MKTPLACE PMTS")
    seed_transaction(connection, "TX-2", "AMAZON PRIME*2X")
    seed_transaction(connection, "TX-3", "CORNER STORE")

    options = keyword_options(connection)
    by_pattern = {(option.match_type, option.pattern): option for option in options.options}

    assert by_pattern[("exact", "AMAZON MKTPLACE PMTS")].matched == 1
    assert by_pattern[("contains", "AMAZON")].matched == 2
    # Candidates come from the clicked row's description alone, so another row's word is not offered.
    assert ("contains", "PRIME") not in by_pattern


def test_keyword_options_are_deterministic() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "ACME PROPERTY MGMT RENT")
    seed_rule(connection, "RENT", "Rent", match_type=constants.MATCH_TYPE_CONTAINS)

    first = keyword_options(connection)
    second = keyword_options(connection)

    assert first == second


def test_keyword_options_reject_an_unknown_transaction() -> None:
    connection = make_connection()

    with pytest.raises(errors.UnknownTransactionError, match="Unknown transaction TX-9"):
        keyword_options(connection, "TX-9")


def category_names(connection: sqlite3.Connection) -> list[str]:
    return [summary.name for summary in service.list_categories(connection)]


def category_positions(connection: sqlite3.Connection) -> dict[str, int]:
    return {summary.name: summary.position for summary in service.list_categories(connection)}


def test_list_categories_reports_counts_and_the_protected_names() -> None:
    """The list the management page renders: display order, usage counts, and which names are built in."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA", "Subscriptions")
    seed_transaction(connection, "TX-2", "SPOTIFY USA", "Subscriptions")
    seed_transaction(connection, "TX-3", "CORNER STORE")
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")

    summaries = service.list_categories(connection)
    by_name = {summary.name: summary for summary in summaries}

    assert [summary.name for summary in summaries] == list(DECLARED_CATEGORIES)
    assert [summary.position for summary in summaries] == list(range(1, 12))
    assert by_name["Subscriptions"].transaction_count == 2
    assert by_name["Subscriptions"].rule_count == 1
    assert by_name["Uncategorized"].transaction_count == 1
    assert by_name["Uncategorized"].rule_count == 0
    assert {summary.name for summary in summaries if summary.is_protected} == {
        constants.TRANSFERS_CATEGORY,
        constants.UNCATEGORIZED_CATEGORY,
    }


def test_create_category_trims_the_name_and_appends_to_the_order() -> None:
    connection = make_connection()

    service.create_category(connection, "  Pets  ")

    created = service.list_categories(connection)[-1]

    assert created.name == "Pets"
    assert created.position == 12
    assert created.transaction_count == 0
    assert created.rule_count == 0
    assert not created.is_protected


@pytest.mark.parametrize("name", ["Groceries", "groceries", "GROCERIES"])
def test_create_category_rejects_a_name_that_is_already_taken(name: str) -> None:
    """Case-insensitively, matching the unique index: two look-alike options in a select is a trap."""
    connection = make_connection()

    with pytest.raises(errors.CategoryNameError, match="already a category"):
        service.create_category(connection, name)

    assert category_names(connection) == list(DECLARED_CATEGORIES)


@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
def test_create_category_rejects_an_empty_or_overlong_name(name: str) -> None:
    connection = make_connection()

    with pytest.raises(errors.CategoryNameError):
        service.create_category(connection, name)

    assert category_names(connection) == list(DECLARED_CATEGORIES)


def test_create_category_rejects_a_slash() -> None:
    """`/api/categories/{name}` cannot address a name holding a slash, so it is refused at the door."""
    connection = make_connection()

    with pytest.raises(errors.CategoryNameError, match="slash"):
        service.create_category(connection, "Food/Drink")

    assert category_names(connection) == list(DECLARED_CATEGORIES)


def test_rename_category_moves_its_rules_and_transactions() -> None:
    """`ON UPDATE CASCADE` does the relabel, so no reclassify pass runs and no position changes."""
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA", "Subscriptions")
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")

    service.rename_category(connection, "Subscriptions", "Streaming")

    by_name = {summary.name: summary for summary in service.list_categories(connection)}

    assert "Subscriptions" not in by_name
    assert by_name["Streaming"].position == 9
    assert by_name["Streaming"].transaction_count == 1
    assert by_name["Streaming"].rule_count == 1
    assert stored_category(connection, "TX-1") == "Streaming"
    assert rule_pairs(connection) == [("exact", "SPOTIFY USA", "Streaming")]


def test_rename_category_allows_a_case_change_of_the_same_name() -> None:
    connection = make_connection()

    service.rename_category(connection, "Groceries", "GROCERIES")

    assert "GROCERIES" in category_names(connection)
    assert "Groceries" not in category_names(connection)


def test_rename_category_rejects_a_taken_name() -> None:
    connection = make_connection()

    with pytest.raises(errors.CategoryNameError, match="already a category"):
        service.rename_category(connection, "Groceries", "dining")

    assert category_names(connection) == list(DECLARED_CATEGORIES)


@pytest.mark.parametrize("name", [constants.TRANSFERS_CATEGORY, constants.UNCATEGORIZED_CATEGORY])
def test_rename_category_refuses_a_protected_name(name: str) -> None:
    connection = make_connection()

    with pytest.raises(errors.ProtectedCategoryError, match="cannot be renamed or deleted"):
        service.rename_category(connection, name, "Something Else")

    assert category_names(connection) == list(DECLARED_CATEGORIES)


def test_rename_category_rejects_an_unknown_name() -> None:
    """Category names are identifiers: `groceries` is not `Groceries`."""
    connection = make_connection()

    with pytest.raises(errors.UnknownCategoryError, match="Unknown category"):
        service.rename_category(connection, "groceries", "Food")

    assert category_names(connection) == list(DECLARED_CATEGORIES)


def test_delete_category_moves_transactions_and_drops_its_rules() -> None:
    connection = make_connection()
    seed_account(connection)
    seed_transaction(connection, "TX-1", "SPOTIFY USA", "Subscriptions")
    seed_transaction(connection, "TX-2", "SPOTIFY USA", "Subscriptions")
    seed_transaction(connection, "TX-3", "CORNER STORE", "Groceries")
    seed_rule(connection, "SPOTIFY USA", "Subscriptions")
    seed_rule(connection, "CORNER STORE", "Groceries")

    result = service.delete_category(connection, "Subscriptions")

    by_name = {summary.name: summary for summary in service.list_categories(connection)}

    assert result.moved_transactions == 2
    assert result.deleted_rules == 1
    assert "Subscriptions" not in by_name
    assert stored_category(connection, "TX-1") == constants.UNCATEGORIZED_CATEGORY
    assert stored_category(connection, "TX-2") == constants.UNCATEGORIZED_CATEGORY
    assert stored_category(connection, "TX-3") == "Groceries"
    assert by_name["Uncategorized"].transaction_count == 2
    assert by_name["Uncategorized"].rule_count == 0
    assert rule_pairs(connection) == [("exact", "CORNER STORE", "Groceries")]
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    # Nothing needs reclassifying afterwards: the reassignment already matches the rules that are left.
    assert service.apply_rules(connection, service.get_category_rules(connection)).updated == 0


def test_delete_category_reports_zero_when_nothing_uses_it() -> None:
    connection = make_connection()

    result = service.delete_category(connection, "Health")

    assert result.moved_transactions == 0
    assert result.deleted_rules == 0
    assert "Health" not in category_names(connection)


def test_deleting_a_category_leaves_its_position_gap_in_place() -> None:
    """Positions order the selects; a gap is harmless and reusing the slot would reorder the list."""
    connection = make_connection()

    service.delete_category(connection, "Dining")
    service.create_category(connection, "Pets")

    positions = category_positions(connection)

    assert positions["Pets"] == 12
    assert "Dining" not in positions
    assert positions["Transport"] == 6


@pytest.mark.parametrize("name", [constants.TRANSFERS_CATEGORY, constants.UNCATEGORIZED_CATEGORY])
def test_delete_category_refuses_a_protected_name(name: str) -> None:
    connection = make_connection()

    with pytest.raises(errors.ProtectedCategoryError, match="cannot be renamed or deleted"):
        service.delete_category(connection, name)

    assert category_names(connection) == list(DECLARED_CATEGORIES)


def test_delete_category_rejects_an_unknown_name() -> None:
    connection = make_connection()

    with pytest.raises(errors.UnknownCategoryError, match="Unknown category"):
        service.delete_category(connection, "groceries")

    assert category_names(connection) == list(DECLARED_CATEGORIES)


def test_reorder_categories_rewrites_every_position_from_the_order_given() -> None:
    """The page sends the whole list, so every position is rewritten and `Transfers` moves too."""
    connection = make_connection()
    ordered_names = ["Dining", *[name for name in DECLARED_CATEGORIES if name != "Dining"]]

    summaries = service.reorder_categories(connection, ordered_names)

    assert [summary.name for summary in summaries] == ordered_names
    assert [summary.position for summary in summaries] == list(range(1, 12))


def test_reorder_categories_closes_the_gap_a_delete_left() -> None:
    connection = make_connection()
    service.delete_category(connection, "Dining")
    remaining = [name for name in DECLARED_CATEGORIES if name != "Dining"]

    service.reorder_categories(connection, [*remaining[1:], remaining[0]])

    positions = category_positions(connection)

    assert positions[remaining[1]] == 1
    assert positions[remaining[0]] == 10
    assert service.create_category(connection, "Pets")[-1].position == 11


@pytest.mark.parametrize(
    "names",
    [
        list(DECLARED_CATEGORIES[:-1]),
        [*DECLARED_CATEGORIES, "Pets"],
        [DECLARED_CATEGORIES[0], *DECLARED_CATEGORIES],
        [],
    ],
)
def test_reorder_categories_rejects_an_order_that_is_not_every_category_once(names: list[str]) -> None:
    """A missing name would lose its place, and a repeat or an extra one would collide on the index."""
    connection = make_connection()

    with pytest.raises(errors.CategoryOrderError, match="exactly once"):
        service.reorder_categories(connection, names)

    assert category_names(connection) == list(DECLARED_CATEGORIES)
