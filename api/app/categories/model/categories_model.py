"""The typed shapes of the categories and rules tables, and what a category operation returns.

Every class that comes out of `categories_persistence` is here, built from a
`sqlite3.Row` by its own `from_row`, so the column names live next to the fields they
fill. Nothing here touches a connection or the wire.
"""

import sqlite3
from dataclasses import dataclass

from app.categories.constants.categories_constants import PROTECTED_CATEGORIES, UNCATEGORIZED_CATEGORY
from app.categories.matching.categories_matching import matches


@dataclass(frozen=True)
class Rule:
    """One stored rule: a pattern, how it matches, and the category it assigns."""

    match_type: str
    pattern: str
    category: str
    updated_at: str

    def matches(self, description: str) -> bool:
        return matches(self.match_type, self.pattern, description)

    @staticmethod
    def from_row(row: sqlite3.Row) -> "Rule":
        return Rule(
            match_type=str(row["match_type"]),
            pattern=str(row["pattern"]),
            category=str(row["category"]),
            updated_at=str(row["updated_at"]),
        )


@dataclass(frozen=True)
class CategoryRules:
    """The closed category list and every rule, most specific first."""

    categories: tuple[str, ...]
    rules: tuple[Rule, ...]

    def classify(self, description: str) -> str:
        """The category of the first (most specific) matching rule, or the unmatched bucket."""
        for rule in self.rules:
            if rule.matches(description):
                return rule.category

        return UNCATEGORIZED_CATEGORY


@dataclass(frozen=True)
class CategoryRow:
    """A category with how many transactions and rules currently carry it."""

    name: str
    position: int
    transaction_count: int
    rule_count: int

    @property
    def is_protected(self) -> bool:
        return self.name in PROTECTED_CATEGORIES

    @staticmethod
    def from_row(row: sqlite3.Row) -> "CategoryRow":
        return CategoryRow(
            name=str(row["name"]),
            position=int(row["position"]),
            transaction_count=int(row["transaction_count"]),
            rule_count=int(row["rule_count"]),
        )


@dataclass(frozen=True)
class ClassificationRow:
    """One stored transaction as the re-classify pass reads it: its key, description and category."""

    connection_id: str
    account_id: str
    transaction_id: str
    description: str
    category: str

    @staticmethod
    def from_row(row: sqlite3.Row) -> "ClassificationRow":
        return ClassificationRow(
            connection_id=str(row["connection_id"]),
            account_id=str(row["account_id"]),
            transaction_id=str(row["transaction_id"]),
            description=str(row["description"]),
            category=str(row["category"]),
        )


@dataclass(frozen=True)
class AssignResult:
    description: str
    match_type: str
    pattern: str
    category: str
    matched: int
    updated: int
    rule_deleted: bool


@dataclass(frozen=True)
class KeywordOption:
    match_type: str
    pattern: str
    category: str | None
    source: str
    matched: int


@dataclass(frozen=True)
class KeywordOptions:
    description: str
    effective_rule: Rule | None
    options: tuple[KeywordOption, ...]


@dataclass(frozen=True)
class ApplyResult:
    updated: int
    uncategorized: int


@dataclass(frozen=True)
class CategoryDeleteResult:
    moved_transactions: int
    deleted_rules: int
