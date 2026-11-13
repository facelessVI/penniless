"""Transaction domain results into wire models, field by field, with no I/O.

The keyword and rule responses live here rather than with categories because the endpoints
that return them are the transaction ones, and categories knows nothing about the wire.
"""

from app.categories.model.categories_model import (
    AssignResult,
    KeywordOption,
    KeywordOptions,
    Rule,
)
from app.transactions.api.transactions_api import (
    SummaryResponse,
    TransactionCategoryResponse,
    TransactionItem,
    TransactionKeywordOption,
    TransactionKeywordResponse,
    TransactionKeywordRule,
    TransactionListResponse,
)
from app.transactions.model.transactions_model import SummaryFigures, Transaction, TransactionPage


def to_summary(figures: SummaryFigures) -> SummaryResponse:
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


def to_transaction(transaction: Transaction) -> TransactionItem:
    return TransactionItem(
        connection_id=transaction.connection_id,
        account_id=transaction.account_id,
        account_name=transaction.account_name,
        transaction_id=transaction.transaction_id,
        posted_date=transaction.posted_date,
        description=transaction.description,
        category=transaction.category,
        amount_cents=transaction.amount_cents,
    )


def to_transaction_list(page: TransactionPage, limit: int, offset: int) -> TransactionListResponse:
    return TransactionListResponse(
        items=[to_transaction(transaction) for transaction in page.transactions],
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


def to_keyword_option(option: KeywordOption) -> TransactionKeywordOption:
    return TransactionKeywordOption(
        match_type=option.match_type,
        pattern=option.pattern,
        category=option.category,
        source=option.source,
        matched=option.matched,
    )


def to_keyword_response(options: KeywordOptions) -> TransactionKeywordResponse:
    effective_rule = options.effective_rule

    return TransactionKeywordResponse(
        description=options.description,
        effective_rule=to_keyword_rule(effective_rule) if effective_rule is not None else None,
        options=[to_keyword_option(option) for option in options.options],
    )


def to_transaction_category(result: AssignResult) -> TransactionCategoryResponse:
    return TransactionCategoryResponse(
        description=result.description,
        match_type=result.match_type,
        pattern=result.pattern,
        category=result.category,
        matched=result.matched,
        updated=result.updated,
        rule_deleted=result.rule_deleted,
    )
