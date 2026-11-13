"""Wire models built from stored rows and domain results.

No I/O and no formatting decisions: every field is spelled out, so a renamed column or a
dropped field fails here rather than reaching the client. Anything that needs a database
call belongs in `ledger`, `categories` or `ingest`.
"""

import sqlite3
from collections.abc import Sequence

from app import ledger
from app.categories import models
from app.categories.constants import UNCATEGORIZED_CATEGORY
from app.categories.matching import Rule
from app.wire.accounts import AccountResponse
from app.wire.categories import (
    ApplyCategoriesResponse,
    CategoriesResponse,
    CategoryDeleteResponse,
    CategoryItem,
)
from app.wire.transactions import (
    SummaryResponse,
    TransactionCategoryResponse,
    TransactionItem,
    TransactionKeywordOption,
    TransactionKeywordResponse,
    TransactionKeywordRule,
    TransactionListResponse,
)


def to_account(row: sqlite3.Row) -> AccountResponse:
    return AccountResponse(
        connection_id=row["connection_id"],
        account_id=row["account_id"],
        connection_name=row["connection_name"],
        name=row["name"],
        currency=row["currency"],
        balance_cents=row["balance_cents"],
        available_balance_cents=row["available_balance_cents"],
        balance_date=row["balance_date"],
        include_in_cash=bool(row["include_in_cash"]),
    )


def to_accounts(rows: Sequence[sqlite3.Row]) -> list[AccountResponse]:
    return [to_account(row) for row in rows]


def to_summary(figures: ledger.SummaryFigures) -> SummaryResponse:
    return SummaryResponse(
        start=figures.start.isoformat(),
        end=figures.end.isoformat(),
        total_in_cents=figures.total_in_cents,
        total_out_cents=figures.total_out_cents,
        net_cents=figures.total_in_cents - figures.total_out_cents,
        cash_total_cents=figures.cash_total_cents,
        net_worth_cents=figures.net_worth_cents,
        transaction_count=figures.transaction_count,
    )


def to_transaction(row: sqlite3.Row) -> TransactionItem:
    return TransactionItem(
        connection_id=row["connection_id"],
        account_id=row["account_id"],
        account_name=row["account_name"],
        transaction_id=row["transaction_id"],
        posted_date=row["posted_date"],
        description=row["description"],
        category=row["category"],
        amount_cents=row["amount_cents"],
    )


def to_transaction_list(page: ledger.TransactionPage, limit: int, offset: int) -> TransactionListResponse:
    return TransactionListResponse(
        items=[to_transaction(row) for row in page.rows],
        total=page.total,
        limit=limit,
        offset=offset,
    )


def to_keyword_rule(rule: Rule) -> TransactionKeywordRule:
    return TransactionKeywordRule(
        match_type=rule.match_type,
        pattern=rule.pattern,
        category=rule.category,
    )


def to_keyword_option(option: models.KeywordOption) -> TransactionKeywordOption:
    return TransactionKeywordOption(
        match_type=option.match_type,
        pattern=option.pattern,
        category=option.category,
        source=option.source,
        matched=option.matched,
    )


def to_keyword_response(options: models.KeywordOptions) -> TransactionKeywordResponse:
    effective_rule = options.effective_rule

    return TransactionKeywordResponse(
        description=options.description,
        effective_rule=to_keyword_rule(effective_rule) if effective_rule is not None else None,
        options=[to_keyword_option(option) for option in options.options],
    )


def to_transaction_category(result: models.AssignResult) -> TransactionCategoryResponse:
    return TransactionCategoryResponse(
        description=result.description,
        match_type=result.match_type,
        pattern=result.pattern,
        category=result.category,
        matched=result.matched,
        updated=result.updated,
        rule_deleted=result.rule_deleted,
    )


def to_category_item(summary: models.CategorySummary) -> CategoryItem:
    return CategoryItem(
        name=summary.name,
        position=summary.position,
        transaction_count=summary.transaction_count,
        rule_count=summary.rule_count,
        protected=summary.is_protected,
    )


def to_categories(summaries: Sequence[models.CategorySummary]) -> CategoriesResponse:
    return CategoriesResponse(
        categories=[to_category_item(summary) for summary in summaries],
        uncategorized=UNCATEGORIZED_CATEGORY,
    )


def to_category_delete(categories: CategoriesResponse, result: models.CategoryDeleteResult) -> CategoryDeleteResponse:
    return CategoryDeleteResponse(
        categories=categories.categories,
        uncategorized=categories.uncategorized,
        moved_transactions=result.moved_transactions,
        deleted_rules=result.deleted_rules,
    )


def to_apply_result(result: models.ApplyResult) -> ApplyCategoriesResponse:
    return ApplyCategoriesResponse(updated=result.updated, uncategorized=result.uncategorized)
