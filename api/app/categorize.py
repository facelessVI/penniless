"""The hand-edited category rules: load, validate, classify, and re-apply over stored rows."""

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app import db
from app.config import settings

UNCATEGORIZED_CATEGORY = "Uncategorized"
SUPPORTED_MATCH_FIELDS = ("description",)
REQUIRED_RULE_KEYS = frozenset({"match", "category"})
OPTIONAL_RULE_KEYS = frozenset({"transfer"})
REQUIRED_TOP_LEVEL_KEYS = frozenset({"categories", "rules"})

UPDATE_CLASSIFICATION_SQL = """
UPDATE transactions SET category = ?, is_transfer = ?, updated_at = ?
WHERE connection_id = ? AND account_id = ? AND transaction_id = ?
"""

SELECT_CLASSIFICATION_SQL = """
SELECT connection_id, account_id, transaction_id, description, category, is_transfer FROM transactions
"""


class CategoryConfigError(ValueError):
    """The rules file is wrong. Raised at startup too, so a bad file cannot cost a fetch."""


@dataclass(frozen=True)
class CategoryRule:
    position: int
    patterns: dict[str, re.Pattern[str]]
    category: str
    transfer: bool

    def matches(self, description: str) -> bool:
        return all(pattern.search(description) is not None for pattern in self.patterns.values())


@dataclass(frozen=True)
class CategoryRules:
    categories: tuple[str, ...]
    rules: tuple[CategoryRule, ...]

    def classify(self, description: str) -> tuple[str, bool]:
        """First match wins; everything else lands in the visible uncategorized bucket."""
        for rule in self.rules:
            if rule.matches(description):
                return rule.category, rule.transfer

        return UNCATEGORIZED_CATEGORY, False


@dataclass(frozen=True)
class ApplyResult:
    updated: int
    uncategorized: int


def load_rules(path: Path | None = None) -> CategoryRules:
    rules_path = path if path is not None else settings.categories_path

    if not rules_path.exists():
        raise CategoryConfigError(f"{rules_path} does not exist.")

    try:
        raw: Any = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise CategoryConfigError(f"{rules_path.name} is not valid YAML: {error}") from error

    if not isinstance(raw, dict):
        raise CategoryConfigError(f"{rules_path.name} must be a mapping with `categories` and `rules`.")

    unknown_keys = set(raw) - REQUIRED_TOP_LEVEL_KEYS

    if unknown_keys:
        raise CategoryConfigError(f"{rules_path.name} has unknown top-level key(s): {', '.join(sorted(unknown_keys))}.")

    missing_keys = REQUIRED_TOP_LEVEL_KEYS - set(raw)

    if missing_keys:
        raise CategoryConfigError(f"{rules_path.name} is missing key(s): {', '.join(sorted(missing_keys))}.")

    categories = parse_categories(raw["categories"], rules_path.name)
    rules = parse_rules(raw["rules"], categories, rules_path.name)

    return CategoryRules(categories=categories, rules=rules)


def parse_categories(raw_categories: Any, filename: str) -> tuple[str, ...]:
    if not isinstance(raw_categories, list) or not raw_categories:
        raise CategoryConfigError(f"{filename} `categories` must be a non-empty list of names.")

    categories: list[str] = []

    for entry in raw_categories:
        if not isinstance(entry, str) or not entry.strip():
            raise CategoryConfigError(f"{filename} `categories` holds an entry that is not a non-empty name.")

        if entry in categories:
            raise CategoryConfigError(f"{filename} declares category {entry!r} twice.")

        categories.append(entry)

    if UNCATEGORIZED_CATEGORY not in categories:
        raise CategoryConfigError(
            f"{filename} must declare {UNCATEGORIZED_CATEGORY!r}, the bucket unmatched transactions land in."
        )

    return tuple(categories)


def parse_rules(raw_rules: Any, categories: tuple[str, ...], filename: str) -> tuple[CategoryRule, ...]:
    if not isinstance(raw_rules, list):
        raise CategoryConfigError(f"{filename} `rules` must be a list.")

    rules: list[CategoryRule] = []

    for offset, entry in enumerate(raw_rules):
        position = offset + 1

        if not isinstance(entry, dict):
            raise CategoryConfigError(f"{filename} rule {position} must be a mapping.")

        unknown_keys = set(entry) - (REQUIRED_RULE_KEYS | OPTIONAL_RULE_KEYS)

        if unknown_keys:
            raise CategoryConfigError(
                f"{filename} rule {position} has unknown key(s): {', '.join(sorted(unknown_keys))}."
            )

        missing_keys = REQUIRED_RULE_KEYS - set(entry)

        if missing_keys:
            raise CategoryConfigError(
                f"{filename} rule {position} is missing key(s): {', '.join(sorted(missing_keys))}."
            )

        patterns = parse_match(entry["match"], position, filename)
        category = entry["category"]

        if not isinstance(category, str):
            raise CategoryConfigError(f"{filename} rule {position} has a `category` that is not a name.")

        if category not in categories:
            raise CategoryConfigError(
                f"{filename} rule {position} references undeclared category {category!r}. "
                f"Declared categories: {', '.join(categories)}."
            )

        transfer = entry.get("transfer", False)

        if not isinstance(transfer, bool):
            raise CategoryConfigError(f"{filename} rule {position} has a `transfer` that is not true or false.")

        rules.append(CategoryRule(position=position, patterns=patterns, category=category, transfer=transfer))

    return tuple(rules)


def parse_match(raw_match: Any, position: int, filename: str) -> dict[str, re.Pattern[str]]:
    if not isinstance(raw_match, dict) or not raw_match:
        raise CategoryConfigError(f"{filename} rule {position} needs a non-empty `match` mapping.")

    patterns: dict[str, re.Pattern[str]] = {}

    for field, pattern in raw_match.items():
        if field not in SUPPORTED_MATCH_FIELDS:
            raise CategoryConfigError(
                f"{filename} rule {position} matches on unsupported field {field!r}. "
                f"Supported fields: {', '.join(SUPPORTED_MATCH_FIELDS)}."
            )

        if not isinstance(pattern, str) or not pattern:
            raise CategoryConfigError(f"{filename} rule {position} has an empty pattern for {field!r}.")

        try:
            patterns[field] = re.compile(pattern)
        except re.error as error:
            raise CategoryConfigError(
                f"{filename} rule {position} has an invalid regex for {field!r}: {error}"
            ) from error

    return patterns


def apply_rules(connection: sqlite3.Connection, rules: CategoryRules) -> ApplyResult:
    """Re-run every rule over every stored row, so categories and transfer flags always match the file."""
    updated = 0
    uncategorized = 0
    updated_at = db.now_iso()
    rows = connection.execute(SELECT_CLASSIFICATION_SQL).fetchall()

    with connection:
        for row in rows:
            category, transfer = rules.classify(row["description"])

            if category == UNCATEGORIZED_CATEGORY:
                uncategorized += 1

            if category == row["category"] and int(transfer) == row["is_transfer"]:
                continue

            connection.execute(
                UPDATE_CLASSIFICATION_SQL,
                (category, int(transfer), updated_at, row["connection_id"], row["account_id"], row["transaction_id"]),
            )
            updated += 1

    return ApplyResult(updated=updated, uncategorized=uncategorized)
