"""The category list and the learned rules: load, validate, classify, re-apply, and manage.

Both live in SQLite rather than a file. A rule is a pattern with a `match_type`: `exact` for the
whole description or `contains` for a case-insensitive literal substring. Every rule that matches a
description is a candidate and the most specific one wins (`exact` first, then the longer pattern,
then the newest rule, then alphabetical), so classification is a small ordered scan rather than a
lookup. Anything no rule matches lands in `Uncategorized`. There is no user-facing regex.

Two names are load-bearing in code rather than data, so they are protected here as well as in the UI:
`Transfers` is how a row is recognized as a transfer, and `Uncategorized` is the fallback bucket that
startup validation requires.

Precedence ordering is the first thing this module does to a rule set; the matching itself lives in
`categories_matching`, the SQL in `categories_persistence`. This module decides what a miss means and
owns every transaction boundary.
"""

import sqlite3
from collections import Counter
from collections.abc import Sequence

from app.categories.constants.categories_constants import (
    CATEGORY_NAME_RULE,
    KEYWORD_SOURCE_DESCRIPTION,
    KEYWORD_SOURCE_PHRASE,
    KEYWORD_SOURCE_RULE,
    KEYWORD_SOURCE_TOKEN,
    MATCH_TYPE_CONTAINS,
    MATCH_TYPE_EXACT,
    MATCH_TYPES,
    PROTECTED_CATEGORY_REASONS,
    UNCATEGORIZED_CATEGORY,
)
from app.categories.errors.categories_errors import (
    CategoryOrderError,
    CategoryRulesError,
    ProtectedCategoryError,
    RulePatternError,
    UnknownCategoryError,
    UnknownRuleError,
    UnknownTransactionError,
)
from app.categories.matching.categories_matching import (
    count_matches,
    keyword_phrases,
    keyword_tokens,
    matches,
)
from app.categories.model.categories_model import (
    ApplyResult,
    AssignResult,
    Category,
    CategoryDeleteResult,
    CategoryRules,
    KeywordOption,
    KeywordOptions,
    Rule,
)
from app.categories.persistence import categories_persistence as persistence
from app.common import db


def order_rules(rules: list[Rule]) -> tuple[Rule, ...]:
    """Most specific first: exact before contains, longer patterns, newest, then alphabetical.

    Python's sort is stable, so each pass refines the one before it: the last sort is the primary key.
    """
    ordered = sorted(rules, key=lambda rule: rule.pattern)
    ordered.sort(key=lambda rule: rule.updated_at, reverse=True)
    ordered.sort(key=lambda rule: len(rule.pattern), reverse=True)
    ordered.sort(key=lambda rule: 0 if rule.match_type == MATCH_TYPE_EXACT else 1)

    return tuple(ordered)


def get_category_rules(connection: sqlite3.Connection) -> CategoryRules:
    """Read and validate the category data. A broken row must fail before it can cost a fetch."""
    categories = tuple(persistence.get_category_names(connection))

    if not categories:
        raise CategoryRulesError("The categories table is empty; the database has lost its category list.")

    if UNCATEGORIZED_CATEGORY not in categories:
        raise CategoryRulesError(
            f"Categories must include {UNCATEGORIZED_CATEGORY!r}, the bucket unmatched transactions land in."
        )

    rules = persistence.get_rules(connection)

    for rule in rules:
        if rule.match_type not in MATCH_TYPES:
            raise CategoryRulesError(
                f"A rule has match type {rule.match_type!r}; the known ones are {', '.join(MATCH_TYPES)}."
            )

        if not rule.pattern.strip():
            raise CategoryRulesError("A rule has an empty pattern.")

        if rule.category not in categories:
            raise CategoryRulesError(f"Rule for {rule.pattern!r} references undeclared category {rule.category!r}.")

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
    rules = get_category_rules(connection)

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

    description = persistence.get_transaction_description(connection, connection_id, account_id, transaction_id)

    if description is None:
        raise UnknownTransactionError(
            f"Unknown transaction {transaction_id} on connection {connection_id}, account {account_id}."
        )

    if not matches(match_type, pattern, description):
        raise RulePatternError(
            f"Keyword {pattern!r} does not occur in the description {description!r} of that transaction."
        )

    matched = count_matches(persistence.get_all_descriptions(connection), match_type, pattern)
    updated_at = db.now_iso()
    is_delete = category == UNCATEGORIZED_CATEGORY

    if is_delete:
        with connection:
            deleted = persistence.delete_rule(connection, match_type, pattern)

        if deleted == 0:
            raise UnknownRuleError(f"There is no {match_type} rule for {pattern!r}.")

        stored_pattern = pattern
    else:
        with connection:
            existing = persistence.get_rule(connection, match_type, pattern)

            if existing is None:
                persistence.insert_rule(connection, match_type, pattern, category, updated_at)
                stored_pattern = pattern
            else:
                # An existing rule keeps its pattern's spelling and its `created_at`; only the
                # category and the timestamp move.
                persistence.update_rule_category(connection, match_type, pattern, category, updated_at)
                stored_pattern = existing

    applied = apply_rules(connection, get_category_rules(connection))

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
    description = persistence.get_transaction_description(connection, connection_id, account_id, transaction_id)

    if description is None:
        raise UnknownTransactionError(
            f"Unknown transaction {transaction_id} on connection {connection_id}, account {account_id}."
        )

    rules = get_category_rules(connection)
    effective_rule = next((rule for rule in rules.rules if rule.matches(description)), None)
    descriptions = persistence.get_all_descriptions(connection)

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
    stored = persistence.get_classifications(connection)

    with connection:
        for transaction_category in stored:
            category = rules.classify(transaction_category.description)

            if category == UNCATEGORIZED_CATEGORY:
                uncategorized += 1

            if category == transaction_category.category:
                continue

            persistence.set_transaction_category(connection, transaction_category, category, updated_at)
            updated += 1

    return ApplyResult(updated=updated, uncategorized=uncategorized)


def list_categories(connection: sqlite3.Connection) -> list[Category]:
    """Every category in display order, with how many transactions and rules currently carry it."""
    return persistence.get_categories_with_counts(connection)


def create_category(connection: sqlite3.Connection, name: str) -> list[Category]:
    """Append a category to the end of the order."""
    normalized = CATEGORY_NAME_RULE.normalize(name)
    ensure_category_name_is_free(connection, normalized)

    with connection:
        persistence.insert_category(connection, normalized)

    return list_categories(connection)


def rename_category(connection: sqlite3.Connection, name: str, new_name: str) -> list[Category]:
    """Rename in place. Both foreign keys carry `ON UPDATE CASCADE`, so rules and rows follow."""
    ensure_category_exists(connection, name)
    ensure_category_is_editable(name)

    normalized = CATEGORY_NAME_RULE.normalize(new_name)
    ensure_category_name_is_free(connection, normalized, current_name=name)

    with connection:
        persistence.rename_category(connection, name, normalized)

    return list_categories(connection)


def delete_category(connection: sqlite3.Connection, name: str) -> CategoryDeleteResult:
    """Move the category's transactions to `Uncategorized`, drop its rules, then drop the category.

    `ON DELETE RESTRICT` would refuse the delete while either table still names the category, and
    moving the rows keeps every transaction rather than losing the ones it held. The list that comes
    back is the one the caller would otherwise have to ask for again.
    """
    ensure_category_exists(connection, name)
    ensure_category_is_editable(name)

    updated_at = db.now_iso()

    with connection:
        moved_transactions = persistence.reassign_category_transactions(
            connection, name, UNCATEGORIZED_CATEGORY, updated_at
        )
        deleted_rules = persistence.delete_category_rules(connection, name)
        persistence.delete_category(connection, name)

    return CategoryDeleteResult(
        categories=list_categories(connection),
        moved_transactions=moved_transactions,
        deleted_rules=deleted_rules,
    )


def reorder_categories(connection: sqlite3.Connection, names: Sequence[str]) -> list[Category]:
    """Rewrite the whole display order as 1..n from the names given, closing any gap a delete left.

    The caller sends the entire list rather than a moved row's neighbours, so a stale client cannot
    leave two categories sharing a place. `position` is UNIQUE, so the old numbers are parked on
    negatives first: writing 1..n straight over them would collide partway through.
    """
    ensure_order_is_every_category_once(names, persistence.get_category_names(connection))

    with connection:
        persistence.invert_category_positions(connection)

        for position, name in enumerate(names, start=1):
            persistence.set_category_position(connection, name, position)

    return list_categories(connection)


def ensure_order_is_every_category_once(names: Sequence[str], stored: Sequence[str]) -> None:
    """A repeat would collide on the unique index and a missing name would lose its place entirely."""
    repeated = sorted(name for name, count in Counter(names).items() if count > 1)
    unknown = sorted(set(names) - set(stored))
    missing = sorted(set(stored) - set(names))
    problems = [
        f"{label}: {', '.join(problems_names)}"
        for label, problems_names in (("repeated", repeated), ("unknown", unknown), ("missing", missing))
        if problems_names
    ]

    if problems:
        raise CategoryOrderError(f"The order must name every category exactly once ({'; '.join(problems)}).")


def ensure_category_exists(connection: sqlite3.Connection, name: str) -> None:
    """Exact match: category names are identifiers and compare case-sensitively."""
    if persistence.get_category(connection, name) is not None:
        return

    raise UnknownCategoryError(f"Unknown category {name!r}.")


def ensure_category_name_is_free(connection: sqlite3.Connection, name: str, current_name: str | None = None) -> None:
    """Case-insensitive, matching the unique index on the table."""
    stored_name = persistence.get_category_case_insensitive(connection, name)

    CATEGORY_NAME_RULE.ensure_is_free(name, stored_name, current_name)


def ensure_category_is_editable(name: str) -> None:
    if name not in PROTECTED_CATEGORY_REASONS:
        return

    raise ProtectedCategoryError(f"{PROTECTED_CATEGORY_REASONS[name]}, so it cannot be renamed or deleted.")
