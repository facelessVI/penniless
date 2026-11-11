"""The category list and the learned rules: load, validate, classify, re-apply, and manage.

Both live in SQLite rather than a file. A rule keys on one exact description, so classification is a
lookup: no ordering, no regex, no first-match-wins. Anything without a rule lands in `Uncategorized`.

Two names are load-bearing in code rather than data, so they are protected here as well as in the UI:
`Transfers` is how a row is recognized as a transfer, and `Uncategorized` is the fallback bucket that
startup validation requires.
"""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

from app import db

UNCATEGORIZED_CATEGORY = "Uncategorized"
TRANSFERS_CATEGORY = "Transfers"
PROTECTED_CATEGORIES = (TRANSFERS_CATEGORY, UNCATEGORIZED_CATEGORY)
PROTECTED_CATEGORY_REASONS = {
    TRANSFERS_CATEGORY: f"{TRANSFERS_CATEGORY!r} decides which rows are transfers",
    UNCATEGORIZED_CATEGORY: f"{UNCATEGORIZED_CATEGORY!r} is where unmatched transactions land",
}
MAXIMUM_CATEGORY_NAME_LENGTH = 40

LOAD_CATEGORIES_SQL = "SELECT name FROM categories ORDER BY position"
LOAD_RULES_SQL = "SELECT description, category FROM rules"

SELECT_CLASSIFICATION_SQL = "SELECT connection_id, account_id, transaction_id, description, category FROM transactions"

SELECT_TRANSACTION_DESCRIPTION_SQL = """
SELECT description FROM transactions
WHERE connection_id = ? AND account_id = ? AND transaction_id = ?
"""

UPSERT_RULE_SQL = """
INSERT INTO rules (description, category, created_at, updated_at) VALUES (?, ?, ?, ?)
ON CONFLICT (description) DO UPDATE SET
    category = excluded.category,
    updated_at = excluded.updated_at
"""

UPDATE_DESCRIPTION_CATEGORY_SQL = "UPDATE transactions SET category = ?, updated_at = ? WHERE description = ?"

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


class CategoryRulesError(ValueError):
    """The category data is wrong. Raised at startup too, so it cannot cost a fetch."""


class UnknownTransactionError(LookupError):
    """The composite key names no stored transaction."""


class CategoryNameError(ValueError):
    """A category name is empty, too long, carries a slash, or is already taken."""


class ProtectedCategoryError(ValueError):
    """The category is named in code, so renaming or deleting it would change behavior."""


class UnknownCategoryError(LookupError):
    """No category has that name."""


@dataclass(frozen=True)
class CategoryRules:
    categories: tuple[str, ...]
    rules: Mapping[str, str]

    def classify(self, description: str) -> str:
        """An exact description match, or the visible bucket unmatched transactions land in."""
        return self.rules.get(description, UNCATEGORIZED_CATEGORY)


@dataclass(frozen=True)
class AssignResult:
    description: str
    category: str
    updated: int


@dataclass(frozen=True)
class ApplyResult:
    updated: int
    uncategorized: int


@dataclass(frozen=True)
class CategorySummary:
    name: str
    position: int
    transaction_count: int
    rule_count: int

    @property
    def is_protected(self) -> bool:
        return self.name in PROTECTED_CATEGORIES


@dataclass(frozen=True)
class CategoryDeleteResult:
    moved_transactions: int
    deleted_rules: int


def load_rules(connection: sqlite3.Connection) -> CategoryRules:
    """Read and validate the category data. A broken row must fail before it can cost a fetch."""
    categories = tuple(row["name"] for row in connection.execute(LOAD_CATEGORIES_SQL))

    if not categories:
        raise CategoryRulesError("The categories table is empty; the database has lost its category list.")

    if UNCATEGORIZED_CATEGORY not in categories:
        raise CategoryRulesError(
            f"Categories must include {UNCATEGORIZED_CATEGORY!r}, the bucket unmatched transactions land in."
        )

    rules: dict[str, str] = {}

    for row in connection.execute(LOAD_RULES_SQL):
        description = row["description"]
        category = row["category"]

        if not description.strip():
            raise CategoryRulesError("A rule has an empty description.")

        if category not in categories:
            raise CategoryRulesError(f"Rule for {description!r} references undeclared category {category!r}.")

        rules[description] = category

    return CategoryRules(categories=categories, rules=rules)


def assign_category(
    connection: sqlite3.Connection,
    connection_id: str,
    account_id: str,
    transaction_id: str,
    category: str,
) -> AssignResult:
    """Teach one description a category: one rule, then every stored row that carries it."""
    rules = load_rules(connection)

    if category not in rules.categories:
        raise CategoryRulesError(
            f"{category!r} is not a declared category. Declared categories: {', '.join(rules.categories)}."
        )

    row = connection.execute(SELECT_TRANSACTION_DESCRIPTION_SQL, (connection_id, account_id, transaction_id)).fetchone()

    if row is None:
        raise UnknownTransactionError(
            f"Unknown transaction {transaction_id} on connection {connection_id}, account {account_id}."
        )

    # The rule keys on the stored description, not on anything the caller sends, so a client cannot
    # widen a rule to a description it was never shown.
    description = str(row["description"])
    updated_at = db.now_iso()

    with connection:
        connection.execute(UPSERT_RULE_SQL, (description, category, updated_at, updated_at))
        cursor = connection.execute(UPDATE_DESCRIPTION_CATEGORY_SQL, (category, updated_at, description))

    return AssignResult(description=description, category=category, updated=cursor.rowcount)


def apply_rules(connection: sqlite3.Connection, rules: CategoryRules) -> ApplyResult:
    """Re-run every rule over every stored row, so categories always match the stored rules."""
    updated = 0
    uncategorized = 0
    updated_at = db.now_iso()
    rows = connection.execute(SELECT_CLASSIFICATION_SQL).fetchall()

    with connection:
        for row in rows:
            category = rules.classify(row["description"])

            if category == UNCATEGORIZED_CATEGORY:
                uncategorized += 1

            if category == row["category"]:
                continue

            connection.execute(
                UPDATE_CLASSIFICATION_SQL,
                (category, updated_at, row["connection_id"], row["account_id"], row["transaction_id"]),
            )
            updated += 1

    return ApplyResult(updated=updated, uncategorized=uncategorized)


def normalize_category_name(name: str) -> str:
    """Trim the ends only: the spacing inside a name is what the user typed."""
    normalized = name.strip()

    if not normalized:
        raise CategoryNameError("A category needs a name.")

    if len(normalized) > MAXIMUM_CATEGORY_NAME_LENGTH:
        raise CategoryNameError(f"A category name can be at most {MAXIMUM_CATEGORY_NAME_LENGTH} characters.")

    # The management endpoints name a category in the path, where a slash would split the segment and
    # turn a valid rename into a 404. Refusing it at the door is clearer than a route that cannot match.
    if "/" in normalized:
        raise CategoryNameError("A category name cannot contain a slash.")

    return normalized


def list_categories(connection: sqlite3.Connection) -> list[CategorySummary]:
    """Every category in display order, with how many transactions and rules currently carry it."""
    return [
        CategorySummary(
            name=row["name"],
            position=row["position"],
            transaction_count=row["transaction_count"],
            rule_count=row["rule_count"],
        )
        for row in connection.execute(SELECT_CATEGORIES_WITH_COUNTS_SQL)
    ]


def create_category(connection: sqlite3.Connection, name: str) -> None:
    """Append a category to the end of the order; positions are never reused."""
    normalized = normalize_category_name(name)
    ensure_category_name_is_free(connection, normalized)

    with connection:
        connection.execute(INSERT_CATEGORY_SQL, (normalized,))


def rename_category(connection: sqlite3.Connection, name: str, new_name: str) -> None:
    """Rename in place. Both foreign keys carry `ON UPDATE CASCADE`, so rules and rows follow."""
    ensure_category_exists(connection, name)
    ensure_category_is_editable(name)

    normalized = normalize_category_name(new_name)
    ensure_category_name_is_free(connection, normalized, current_name=name)

    with connection:
        connection.execute(RENAME_CATEGORY_SQL, (normalized, name))


def delete_category(connection: sqlite3.Connection, name: str) -> CategoryDeleteResult:
    """Move the category's transactions to `Uncategorized`, drop its rules, then drop the category.

    `ON DELETE RESTRICT` would refuse the delete while either table still names the category, and
    moving the rows keeps every transaction rather than losing the ones it held.
    """
    ensure_category_exists(connection, name)
    ensure_category_is_editable(name)

    updated_at = db.now_iso()

    with connection:
        transactions_cursor = connection.execute(
            REASSIGN_CATEGORY_TRANSACTIONS_SQL, (UNCATEGORIZED_CATEGORY, updated_at, name)
        )
        rules_cursor = connection.execute(DELETE_CATEGORY_RULES_SQL, (name,))
        connection.execute(DELETE_CATEGORY_SQL, (name,))

    return CategoryDeleteResult(moved_transactions=transactions_cursor.rowcount, deleted_rules=rules_cursor.rowcount)


def ensure_category_exists(connection: sqlite3.Connection, name: str) -> None:
    """Exact match: category names are identifiers and compare case-sensitively."""
    if connection.execute(SELECT_CATEGORY_SQL, (name,)).fetchone() is not None:
        return

    raise UnknownCategoryError(f"Unknown category {name!r}.")


def ensure_category_name_is_free(connection: sqlite3.Connection, name: str, current_name: str | None = None) -> None:
    """Case-insensitive, matching the unique index on the table."""
    row = connection.execute(SELECT_CATEGORY_CASE_INSENSITIVE_SQL, (name,)).fetchone()

    if row is None or row["name"] == current_name:
        return

    raise CategoryNameError(f"{name!r} is already a category.")


def ensure_category_is_editable(name: str) -> None:
    if name not in PROTECTED_CATEGORY_REASONS:
        return

    raise ProtectedCategoryError(f"{PROTECTED_CATEGORY_REASONS[name]}, so it cannot be renamed or deleted.")
