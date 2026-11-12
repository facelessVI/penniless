"""The category list and the learned rules: load, validate, classify, re-apply, and manage.

Both live in SQLite rather than a file. A rule is a pattern with a `match_type`: `exact` for the
whole description or `contains` for a case-insensitive literal substring. Every rule that matches a
description is a candidate and the most specific one wins (`exact` first, then the longer pattern,
then the newest rule, then alphabetical), so classification is a small ordered scan rather than a
lookup. Anything no rule matches lands in `Uncategorized`. There is no user-facing regex.

Two names are load-bearing in code rather than data, so they are protected here as well as in the UI:
`Transfers` is how a row is recognized as a transfer, and `Uncategorized` is the fallback bucket that
startup validation requires.
"""

import sqlite3
import string
from collections.abc import Sequence
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

MATCH_TYPE_EXACT = "exact"
MATCH_TYPE_CONTAINS = "contains"
MATCH_TYPES = (MATCH_TYPE_EXACT, MATCH_TYPE_CONTAINS)

KEYWORD_SOURCE_DESCRIPTION = "description"
KEYWORD_SOURCE_RULE = "rule"
KEYWORD_SOURCE_TOKEN = "token"
KEYWORD_SOURCE_PHRASE = "phrase"
MINIMUM_KEYWORD_TOKEN_LENGTH = 3

# Words that say how a charge arrived rather than who it was to. Kept short on purpose: dropping a
# merchant word hides the keyword the user actually wants.
KEYWORD_NOISE_TOKENS = frozenset(
    {
        "ach",
        "amex",
        "autopay",
        "card",
        "debit",
        "discover",
        "mastercard",
        "payment",
        "pending",
        "pmts",
        "pos",
        "purchase",
        "ref",
        "recurring",
        "visa",
    }
)

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


class RulePatternError(ValueError):
    """A keyword is blank, has an unknown match type, or does not occur in the description shown."""


class UnknownRuleError(LookupError):
    """Nothing to delete: no rule of that type carries that keyword."""


def matches(match_type: str, pattern: str, description: str) -> bool:
    """`exact` is the whole description and stays case-sensitive; `contains` is a substring."""
    if match_type == MATCH_TYPE_EXACT:
        return pattern == description

    return pattern.casefold() in description.casefold()


def count_matches(descriptions: Sequence[str], match_type: str, pattern: str) -> int:
    """How many stored rows a candidate rule would match, through the same helper classify uses."""
    return sum(1 for description in descriptions if matches(match_type, pattern, description))


def keyword_token(word: str) -> str | None:
    """One word as a keyword, or `None` when it says nothing about the merchant."""
    token = word.strip(string.punctuation)

    if len(token) < MINIMUM_KEYWORD_TOKEN_LENGTH:
        return None

    if any(character.isdigit() for character in token):
        return None

    if not any(character.isalpha() for character in token):
        return None

    if token.casefold() in KEYWORD_NOISE_TOKENS:
        return None

    return token


def keyword_tokens(description: str) -> list[str]:
    """The description's words a keyword could plausibly be: no digits, no short words, no noise."""
    return [token for word in description.split() if (token := keyword_token(word)) is not None]


def keyword_phrases(description: str) -> list[str]:
    """Two neighbouring words, so a merchant whose useful part spans a boundary is still offered.

    Adjacency is read from the description, not from the filtered word list, and the phrase is only
    kept when it occurs in the description as written. Sorting the words first would offer pairs the
    user never saw and that match nothing.
    """
    words = description.split()
    qualifiers = [keyword_token(word) for word in words]
    phrases: list[str] = []

    for index in range(len(words) - 1):
        first = qualifiers[index]
        second = qualifiers[index + 1]

        if first is None or second is None:
            continue

        phrase = f"{first} {second}"

        if phrase.casefold() not in description.casefold():
            continue

        phrases.append(phrase)

    return phrases


@dataclass(frozen=True)
class Rule:
    match_type: str
    pattern: str
    category: str
    updated_at: str

    def matches(self, description: str) -> bool:
        return matches(self.match_type, self.pattern, description)


@dataclass(frozen=True)
class CategoryRules:
    categories: tuple[str, ...]
    rules: tuple[Rule, ...]

    def classify(self, description: str) -> str:
        """The category of the first (most specific) matching rule, or the unmatched bucket."""
        for rule in self.rules:
            if rule.matches(description):
                return rule.category

        return UNCATEGORIZED_CATEGORY


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


def order_rules(rules: list[Rule]) -> tuple[Rule, ...]:
    """Most specific first: exact before contains, longer patterns, newest, then alphabetical.

    Python's sort is stable, so each pass refines the one before it: the last sort is the primary key.
    """
    ordered = sorted(rules, key=lambda rule: rule.pattern)
    ordered.sort(key=lambda rule: rule.updated_at, reverse=True)
    ordered.sort(key=lambda rule: len(rule.pattern), reverse=True)
    ordered.sort(key=lambda rule: 0 if rule.match_type == MATCH_TYPE_EXACT else 1)

    return tuple(ordered)


def load_rules(connection: sqlite3.Connection) -> CategoryRules:
    """Read and validate the category data. A broken row must fail before it can cost a fetch."""
    categories = tuple(row["name"] for row in connection.execute(LOAD_CATEGORIES_SQL))

    if not categories:
        raise CategoryRulesError("The categories table is empty; the database has lost its category list.")

    if UNCATEGORIZED_CATEGORY not in categories:
        raise CategoryRulesError(
            f"Categories must include {UNCATEGORIZED_CATEGORY!r}, the bucket unmatched transactions land in."
        )

    rules: list[Rule] = []

    for row in connection.execute(LOAD_RULES_SQL):
        match_type = str(row["match_type"])
        pattern = str(row["pattern"])
        category = str(row["category"])

        if match_type not in MATCH_TYPES:
            raise CategoryRulesError(
                f"A rule has match type {match_type!r}; the known ones are {', '.join(MATCH_TYPES)}."
            )

        if not pattern.strip():
            raise CategoryRulesError("A rule has an empty pattern.")

        if category not in categories:
            raise CategoryRulesError(f"Rule for {pattern!r} references undeclared category {category!r}.")

        rules.append(Rule(match_type=match_type, pattern=pattern, category=category, updated_at=str(row["updated_at"])))

    return CategoryRules(categories=categories, rules=order_rules(rules))


def assign_category(
    connection: sqlite3.Connection,
    connection_id: str,
    account_id: str,
    transaction_id: str,
    category: str,
    match_type: str,
    pattern: str,
) -> AssignResult:
    """Teach one keyword a category, or delete its rule when the category is `Uncategorized`.

    The keyword has to occur in the stored description of the row the caller named, so a client can
    never widen a rule to a description it was never shown. The whole rule set is then re-applied, so
    precedence resolves any overlap rather than the write order deciding it.
    """
    rules = load_rules(connection)

    if category not in rules.categories:
        raise CategoryRulesError(
            f"{category!r} is not a declared category. Declared categories: {', '.join(rules.categories)}."
        )

    if match_type not in MATCH_TYPES:
        raise RulePatternError(
            f"{match_type!r} is not a known match type. The known ones are: {', '.join(MATCH_TYPES)}."
        )

    if not pattern.strip():
        raise RulePatternError("A keyword cannot be blank.")

    row = connection.execute(SELECT_TRANSACTION_DESCRIPTION_SQL, (connection_id, account_id, transaction_id)).fetchone()

    if row is None:
        raise UnknownTransactionError(
            f"Unknown transaction {transaction_id} on connection {connection_id}, account {account_id}."
        )

    description = str(row["description"])

    if not matches(match_type, pattern, description):
        raise RulePatternError(
            f"Keyword {pattern!r} does not occur in the description {description!r} of that transaction."
        )

    matched = count_matches(
        [str(stored["description"]) for stored in connection.execute(SELECT_ALL_DESCRIPTIONS_SQL)], match_type, pattern
    )
    updated_at = db.now_iso()
    is_delete = category == UNCATEGORIZED_CATEGORY

    if is_delete:
        with connection:
            cursor = connection.execute(DELETE_RULE_SQL, (match_type, pattern))

        if cursor.rowcount == 0:
            raise UnknownRuleError(f"There is no {match_type} rule for {pattern!r}.")

        stored_pattern = pattern
    else:
        with connection:
            existing = connection.execute(SELECT_RULE_SQL, (match_type, pattern)).fetchone()

            if existing is None:
                connection.execute(INSERT_RULE_SQL, (match_type, pattern, category, updated_at, updated_at))
                stored_pattern = pattern
            else:
                # An existing rule keeps its pattern's spelling and its `created_at`; only the
                # category and the timestamp move.
                connection.execute(UPDATE_RULE_SQL, (category, updated_at, match_type, pattern))
                stored_pattern = str(existing["pattern"])

    applied = apply_rules(connection, load_rules(connection))

    return AssignResult(
        description=description,
        match_type=match_type,
        pattern=stored_pattern,
        category=category,
        matched=matched,
        updated=applied.updated,
        rule_deleted=is_delete,
    )


def list_keyword_options(
    connection: sqlite3.Connection, connection_id: str, account_id: str, transaction_id: str
) -> KeywordOptions:
    """The keyword candidates for one transaction, with the rows each one would match.

    Order is fixed so the dialog cannot reshuffle between opens: the whole description first, then
    the rules that already match it (most specific first), then the description's words, then its
    two-word phrases. A candidate that appears twice collapses into the first source that offered it,
    which is what keeps an existing rule's category visible instead of a bare token beside it.
    """
    row = connection.execute(SELECT_TRANSACTION_DESCRIPTION_SQL, (connection_id, account_id, transaction_id)).fetchone()

    if row is None:
        raise UnknownTransactionError(
            f"Unknown transaction {transaction_id} on connection {connection_id}, account {account_id}."
        )

    description = str(row["description"])
    rules = load_rules(connection)
    effective_rule = next((rule for rule in rules.rules if rule.matches(description)), None)
    descriptions = [str(stored["description"]) for stored in connection.execute(SELECT_ALL_DESCRIPTIONS_SQL)]

    exact_rule = next(
        (rule for rule in rules.rules if rule.match_type == MATCH_TYPE_EXACT and rule.pattern == description),
        None,
    )
    candidates: list[tuple[str, str, str | None, str]] = [
        (
            MATCH_TYPE_EXACT,
            description,
            exact_rule.category if exact_rule is not None else None,
            KEYWORD_SOURCE_DESCRIPTION,
        )
    ]

    for rule in rules.rules:
        if rule.match_type == MATCH_TYPE_EXACT and rule.pattern == description:
            continue

        if rule.matches(description):
            candidates.append((rule.match_type, rule.pattern, rule.category, KEYWORD_SOURCE_RULE))

    for token in sorted(keyword_tokens(description), key=str.casefold):
        candidates.append((MATCH_TYPE_CONTAINS, token, None, KEYWORD_SOURCE_TOKEN))

    for phrase in keyword_phrases(description):
        candidates.append((MATCH_TYPE_CONTAINS, phrase, None, KEYWORD_SOURCE_PHRASE))

    seen: set[tuple[str, str]] = set()
    options: list[KeywordOption] = []

    for match_type, pattern, category, source in candidates:
        key = (match_type, pattern.casefold())

        if key in seen:
            continue

        seen.add(key)
        options.append(
            KeywordOption(
                match_type=match_type,
                pattern=pattern,
                category=category,
                source=source,
                matched=count_matches(descriptions, match_type, pattern),
            )
        )

    return KeywordOptions(description=description, effective_rule=effective_rule, options=tuple(options))


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
