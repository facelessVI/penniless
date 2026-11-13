"""Period summary and the filtered transaction list."""

import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app import converters, db, ledger
from app.categories import service
from app.schemas import (
    SummaryResponse,
    TransactionCategoryRequest,
    TransactionCategoryResponse,
    TransactionKeywordResponse,
    TransactionListResponse,
)

router = APIRouter(tags=["transactions"])


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    start: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
    end: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
) -> SummaryResponse:
    range_start, range_end = ledger.resolve_summary_range(start, end)

    return converters.to_summary(ledger.get_summary_figures(connection, range_start, range_end))


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    account_id: Annotated[str | None, Query(description="Restrict to one account")] = None,
    category: Annotated[str | None, Query(description="Exact category name")] = None,
    start: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
    end: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
    include_transfers: Annotated[bool, Query(description="Include rows flagged as transfers")] = False,
    limit: Annotated[int, Query(ge=1, le=ledger.MAXIMUM_PAGE_SIZE)] = ledger.DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    ledger.validate_range(start, end)

    filters = ledger.TransactionFilters(
        account_id=account_id,
        category=category,
        start=start,
        end=end,
        include_transfers=include_transfers,
    )
    page = ledger.find_transaction_page(connection, filters, limit, offset)

    return converters.to_transaction_list(page, limit, offset)


@router.get("/transactions/keywords", response_model=TransactionKeywordResponse)
def list_transaction_keywords(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    connection_id: Annotated[str, Query(description="The transaction's connection")],
    account_id: Annotated[str, Query(description="The transaction's account")],
    transaction_id: Annotated[str, Query(description="The transaction's id")],
) -> TransactionKeywordResponse:
    options = service.list_keyword_options(connection, connection_id, account_id, transaction_id)

    return converters.to_keyword_response(options)


@router.post("/transactions/category", response_model=TransactionCategoryResponse)
def assign_transaction_category(
    request: TransactionCategoryRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> TransactionCategoryResponse:
    result = service.assign_category(
        connection,
        request.connection_id,
        request.account_id,
        request.transaction_id,
        request.category,
        request.match_type,
        request.pattern,
    )

    return converters.to_transaction_category(result)
