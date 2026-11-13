"""Every SQL statement about categories and rules.

One function, one statement, and no decisions: a miss comes back as `None` or a row count,
and the service decides what a miss means. The transaction boundary belongs to the service
too, which is why nothing here opens one.
"""

import sqlite3

LOAD_CATEGORIES_SQL = "SELECT name FROM categories ORDER BY position"
LOAD_RULES_SQL = "SELECT match_type, pattern, category, updated_at FROM rules"

SELECT_CLASSIFICATION_SQL = "SELECT connection_id, account_id, transaction_id, description, category FROM transactions"

SELECT_TRANSACTION_DESCRIPTION_SQL = """
SELECT description FROM transactions
WHERE connection_id = ? AND account_id = ? AND transaction_id = ?
"""

SELECT_ALL_DESCRIPTIONS_SQL = "SELECT description FROM transactions"

SELECT_RULE_SQL = "SELECT pattern, category FROM rules WHERE match_type = ? AND pattern = ? COLLATE NOCASE"

INSERT_RULE_SQL = "INSERT INTO rules (match_type, pattern, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"

UPDATE_RULE_SQL = "UPDATE rules SET category = ?, updated_at = ? WHERE match_type = ? AND pattern = ? COLLATE NOCASE"

DELETE_RULE_SQL = "DELETE FROM rules WHERE match_type = ? AND pattern = ? COLLATE NOCASE"

UPDATE_CLASSIFICATION_SQL = """
UPDATE transactions SET category = ?, updated_at = ?
WHERE connection_id = ? AND account_id = ? AND transaction_id = ?
"""

SELECT_CATEGORIES_WITH_COUNTS_SQL = """
SELECT
    categories.name,
    categories.position,
    (SELECT count(*) FROM transactions WHERE transactions.category = categories.name) AS transaction_count,
    (SELECT count(*) FROM rules WHERE rules.category = categories.name) AS rule_count
FROM categories
ORDER BY categories.position
"""

SELECT_CATEGORY_SQL = "SELECT name FROM categories WHERE name = ?"

SELECT_CATEGORY_CASE_INSENSITIVE_SQL = "SELECT name FROM categories WHERE name = ? COLLATE NOCASE"

INSERT_CATEGORY_SQL = """
INSERT INTO categories (name, position) VALUES (?, (SELECT coalesce(max(position), 0) + 1 FROM categories))
"""

RENAME_CATEGORY_SQL = "UPDATE categories SET name = ? WHERE name = ?"

REASSIGN_CATEGORY_TRANSACTIONS_SQL = "UPDATE transactions SET category = ?, updated_at = ? WHERE category = ?"

DELETE_CATEGORY_RULES_SQL = "DELETE FROM rules WHERE category = ?"

DELETE_CATEGORY_SQL = "DELETE FROM categories WHERE name = ?"


def get_category_names(connection: sqlite3.Connection) -> list[str]:
    return [str(row["name"]) for row in connection.execute(LOAD_CATEGORIES_SQL)]


def get_rule_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(LOAD_RULES_SQL).fetchall()


def get_transaction_description(
    connection: sqlite3.Connection, connection_id: str, account_id: str, transaction_id: str
) -> str | None:
    row = connection.execute(SELECT_TRANSACTION_DESCRIPTION_SQL, (connection_id, account_id, transaction_id)).fetchone()

    return None if row is None else str(row["description"])


def get_all_descriptions(connection: sqlite3.Connection) -> list[str]:
    return [str(row["description"]) for row in connection.execute(SELECT_ALL_DESCRIPTIONS_SQL)]


def get_classification_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(SELECT_CLASSIFICATION_SQL).fetchall()


def set_transaction_category(
    connection: sqlite3.Connection,
    connection_id: str,
    account_id: str,
    transaction_id: str,
    category: str,
    updated_at: str,
) -> None:
    connection.execute(UPDATE_CLASSIFICATION_SQL, (category, updated_at, connection_id, account_id, transaction_id))


def get_rule(connection: sqlite3.Connection, match_type: str, pattern: str) -> sqlite3.Row | None:
    return connection.execute(SELECT_RULE_SQL, (match_type, pattern)).fetchone()


def insert_rule(connection: sqlite3.Connection, match_type: str, pattern: str, category: str, updated_at: str) -> None:
    connection.execute(INSERT_RULE_SQL, (match_type, pattern, category, updated_at, updated_at))


def update_rule_category(
    connection: sqlite3.Connection, match_type: str, pattern: str, category: str, updated_at: str
) -> None:
    connection.execute(UPDATE_RULE_SQL, (category, updated_at, match_type, pattern))


def delete_rule(connection: sqlite3.Connection, match_type: str, pattern: str) -> int:
    return connection.execute(DELETE_RULE_SQL, (match_type, pattern)).rowcount


def get_categories_with_counts(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(SELECT_CATEGORIES_WITH_COUNTS_SQL).fetchall()


def get_category(connection: sqlite3.Connection, name: str) -> str | None:
    row = connection.execute(SELECT_CATEGORY_SQL, (name,)).fetchone()

    return None if row is None else str(row["name"])


def get_category_case_insensitive(connection: sqlite3.Connection, name: str) -> str | None:
    row = connection.execute(SELECT_CATEGORY_CASE_INSENSITIVE_SQL, (name,)).fetchone()

    return None if row is None else str(row["name"])


def insert_category(connection: sqlite3.Connection, name: str) -> None:
    connection.execute(INSERT_CATEGORY_SQL, (name,))


def rename_category(connection: sqlite3.Connection, name: str, new_name: str) -> None:
    connection.execute(RENAME_CATEGORY_SQL, (new_name, name))


def reassign_category_transactions(
    connection: sqlite3.Connection, from_name: str, to_name: str, updated_at: str
) -> int:
    return connection.execute(REASSIGN_CATEGORY_TRANSACTIONS_SQL, (to_name, updated_at, from_name)).rowcount


def delete_category_rules(connection: sqlite3.Connection, name: str) -> int:
    return connection.execute(DELETE_CATEGORY_RULES_SQL, (name,)).rowcount


def delete_category(connection: sqlite3.Connection, name: str) -> None:
    connection.execute(DELETE_CATEGORY_SQL, (name,))
