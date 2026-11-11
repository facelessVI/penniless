"""The category list and the learned rules: load, validate, classify, and re-apply over stored rows.

Both live in SQLite rather than a file. A rule keys on one exact description, so classification is a
lookup: no ordering, no regex, no first-match-wins. Anything without a rule lands in `Uncategorized`.
"""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

from app import db

UNCATEGORIZED_CATEGORY = "Uncategorized"
TRANSFERS_CATEGORY = "Transfers"

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


class CategoryRulesError(ValueError):
    """The category data is wrong. Raised at startup too, so it cannot cost a fetch."""


class UnknownTransactionError(LookupError):
    """The composite key names no stored transaction."""


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
