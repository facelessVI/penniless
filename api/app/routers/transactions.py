"""Period summary and the filtered transaction list."""

import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app import categorize, db
from app.schemas import (
    SummaryResponse,
    TransactionCategoryRequest,
    TransactionCategoryResponse,
    TransactionItem,
    TransactionKeywordOption,
    TransactionKeywordResponse,
    TransactionKeywordRule,
    TransactionListResponse,
)

router = APIRouter(tags=["transactions"])

DEFAULT_PAGE_SIZE = 200
MAXIMUM_PAGE_SIZE = 200

SUMMARY_SQL = """
SELECT
    coalesce(
        sum(CASE WHEN category <> :transfers AND amount_cents > 0 THEN amount_cents END), 0
    ) AS total_in_cents,
    coalesce(
        -sum(CASE WHEN category <> :transfers AND amount_cents < 0 THEN amount_cents END), 0
    ) AS total_out_cents,
    count(*) AS transaction_count
FROM transactions
WHERE posted_date BETWEEN :start AND :end
"""

CASH_TOTAL_SQL = "SELECT coalesce(sum(balance_cents), 0) AS cash_total_cents FROM accounts WHERE include_in_cash = 1"

NET_WORTH_SQL = "SELECT coalesce(sum(balance_cents), 0) AS net_worth_cents FROM accounts"

TRANSACTION_COLUMNS = """
    t.connection_id, t.account_id, a.name AS account_name, t.transaction_id, t.posted_date,
    t.description, t.category, t.amount_cents
"""

TRANSACTION_FROM_SQL = """
FROM transactions t
JOIN accounts a ON a.connection_id = t.connection_id AND a.account_id = t.account_id
"""


def resolve_summary_range(start: date | None, end: date | None) -> tuple[date, date]:
    """Both dates are inclusive and read in machine local time; the default is the current month."""
    today = date.today()
    range_start = start or today.replace(day=1)
    range_end = end or today

    if range_start > range_end:
        raise HTTPException(status_code=400, detail="start must be on or before end.")

    return range_start, range_end


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    start: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
    end: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
) -> SummaryResponse:
    range_start, range_end = resolve_summary_range(start, end)
    parameters = {
        "transfers": categorize.TRANSFERS_CATEGORY,
        "start": range_start.isoformat(),
        "end": range_end.isoformat(),
    }
    row = connection.execute(SUMMARY_SQL, parameters).fetchone()
    cash_row = connection.execute(CASH_TOTAL_SQL).fetchone()
    net_worth_row = connection.execute(NET_WORTH_SQL).fetchone()
    total_in_cents = int(row["total_in_cents"])
    total_out_cents = int(row["total_out_cents"])

    return SummaryResponse(
        start=range_start.isoformat(),
        end=range_end.isoformat(),
        total_in_cents=total_in_cents,
        total_out_cents=total_out_cents,
        net_cents=total_in_cents - total_out_cents,
        cash_total_cents=int(cash_row["cash_total_cents"]),
        net_worth_cents=int(net_worth_row["net_worth_cents"]),
        transaction_count=int(row["transaction_count"]),
    )


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    account_id: Annotated[str | None, Query(description="Restrict to one account")] = None,
    category: Annotated[str | None, Query(description="Exact category name")] = None,
    start: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
    end: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
    include_transfers: Annotated[bool, Query(description="Include rows flagged as transfers")] = False,
    limit: Annotated[int, Query(ge=1, le=MAXIMUM_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=400, detail="start must be on or before end.")

    clauses: list[str] = []
    parameters: list[object] = []

    if account_id is not None:
        clauses.append("t.account_id = ?")
        parameters.append(account_id)

    if category is not None:
        clauses.append("t.category = ?")
        parameters.append(category)

    if start is not None:
        clauses.append("t.posted_date >= ?")
        parameters.append(start.isoformat())

    if end is not None:
        clauses.append("t.posted_date <= ?")
        parameters.append(end.isoformat())

    if not include_transfers:
        clauses.append("t.category <> ?")
        parameters.append(categorize.TRANSFERS_CATEGORY)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    total_row = connection.execute(
        f"SELECT count(*) AS total {TRANSACTION_FROM_SQL} {where_sql}", parameters
    ).fetchone()
    rows = connection.execute(
        f"SELECT {TRANSACTION_COLUMNS} {TRANSACTION_FROM_SQL} {where_sql} "
        "ORDER BY t.posted_date DESC, t.transaction_id DESC LIMIT ? OFFSET ?",
        [*parameters, limit, offset],
    ).fetchall()

    items = [
        TransactionItem(
            connection_id=row["connection_id"],
            account_id=row["account_id"],
            account_name=row["account_name"],
            transaction_id=row["transaction_id"],
            posted_date=row["posted_date"],
            description=row["description"],
            category=row["category"],
            amount_cents=row["amount_cents"],
        )
        for row in rows
    ]

    return TransactionListResponse(items=items, total=int(total_row["total"]), limit=limit, offset=offset)


@router.get("/transactions/keywords", response_model=TransactionKeywordResponse)
def list_transaction_keywords(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    connection_id: Annotated[str, Query(description="The transaction's connection")],
    account_id: Annotated[str, Query(description="The transaction's account")],
    transaction_id: Annotated[str, Query(description="The transaction's id")],
) -> TransactionKeywordResponse:
    options = categorize.list_keyword_options(connection, connection_id, account_id, transaction_id)

    return to_keyword_response(options)


@router.post("/transactions/category", response_model=TransactionCategoryResponse)
def assign_transaction_category(
    request: TransactionCategoryRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> TransactionCategoryResponse:
    result = categorize.assign_category(
        connection,
        request.connection_id,
        request.account_id,
        request.transaction_id,
        request.category,
        request.match_type,
        request.pattern,
    )

    return TransactionCategoryResponse(
        description=result.description,
        match_type=result.match_type,
        pattern=result.pattern,
        category=result.category,
        matched=result.matched,
        updated=result.updated,
        rule_deleted=result.rule_deleted,
    )


def to_keyword_response(options: categorize.KeywordOptions) -> TransactionKeywordResponse:
    effective_rule = options.effective_rule

    return TransactionKeywordResponse(
        description=options.description,
        effective_rule=(
            TransactionKeywordRule(
                match_type=effective_rule.match_type,
                pattern=effective_rule.pattern,
                category=effective_rule.category,
            )
            if effective_rule is not None
            else None
        ),
        options=[
            TransactionKeywordOption(
                match_type=option.match_type,
                pattern=option.pattern,
                category=option.category,
                source=option.source,
                matched=option.matched,
            )
            for option in options.options
        ],
    )
