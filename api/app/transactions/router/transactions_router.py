"""Period summary, the filtered transaction list, and the rules learned from a transaction."""

import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.categories.service import categories_service as category_service
from app.common import db
from app.transactions.api.transactions_api import (
    SummaryResponse,
    TransactionCategoryRequest,
    TransactionCategoryResponse,
    TransactionKeywordResponse,
    TransactionListResponse,
)
from app.transactions.constants.transactions_constants import DEFAULT_PAGE_SIZE, MAXIMUM_PAGE_SIZE
from app.transactions.converter import transactions_converter as converter
from app.transactions.model.transactions_model import TransactionFilters
from app.transactions.service import transactions_service as service

router = APIRouter(tags=["transactions"])


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    start: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
    end: Annotated[date | None, Query(description="Inclusive ISO date")] = None,
) -> SummaryResponse:
    return converter.to_summary(service.get_summary(connection, start, end))


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
    filters = TransactionFilters(
        account_id=account_id,
        category=category,
        start=start,
        end=end,
        include_transfers=include_transfers,
    )

    return converter.to_transaction_list(service.find_transactions(connection, filters, limit, offset), limit, offset)


@router.get("/transactions/keywords", response_model=TransactionKeywordResponse)
def list_transaction_keywords(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
    connection_id: Annotated[str, Query(description="The transaction's connection")],
    account_id: Annotated[str, Query(description="The transaction's account")],
    transaction_id: Annotated[str, Query(description="The transaction's id")],
) -> TransactionKeywordResponse:
    options = category_service.list_keyword_options(connection, connection_id, account_id, transaction_id)

    return converter.to_keyword_response(options)


@router.post("/transactions/category", response_model=TransactionCategoryResponse)
def assign_transaction_category(
    request: TransactionCategoryRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> TransactionCategoryResponse:
    result = category_service.assign_category(
        connection,
        request.connection_id,
        request.account_id,
        request.transaction_id,
        request.category,
        request.match_type,
        request.pattern,
    )

    return converter.to_transaction_category(result)
