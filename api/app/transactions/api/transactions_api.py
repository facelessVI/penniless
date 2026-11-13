"""The period summary, the transaction list, and the keyword-and-rule models the dialog uses."""

from app.common.api_model import ApiModel


class SummaryResponse(ApiModel):
    start: str
    end: str
    total_in_cents: int
    total_out_cents: int
    net_cents: int
    cash_total_cents: int
    net_worth_cents: int
    transaction_count: int


class TransactionItem(ApiModel):
    connection_id: str
    account_id: str
    account_name: str
    transaction_id: str
    posted_date: str
    description: str
    category: str
    amount_cents: int


class TransactionListResponse(ApiModel):
    items: list[TransactionItem]
    total: int
    limit: int
    offset: int


class TransactionCategoryRequest(ApiModel):
    connection_id: str
    account_id: str
    transaction_id: str
    match_type: str
    pattern: str
    category: str


class TransactionCategoryResponse(ApiModel):
    description: str
    match_type: str
    pattern: str
    category: str
    matched: int
    updated: int
    rule_deleted: bool


class TransactionKeywordRule(ApiModel):
    match_type: str
    pattern: str
    category: str


class TransactionKeywordOption(ApiModel):
    match_type: str
    pattern: str
    category: str | None
    source: str
    matched: int


class TransactionKeywordResponse(ApiModel):
    description: str
    effective_rule: TransactionKeywordRule | None
    options: list[TransactionKeywordOption]
