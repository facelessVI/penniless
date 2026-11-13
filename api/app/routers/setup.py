"""Setup endpoints: health, connection status, connect, refresh, backfill."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.accounts.persistence import accounts_persistence
from app.common import credentials, db, errors, simplefin
from app.common.config import settings
from app.fetches.persistence import fetches_persistence
from app.fetches.service import fetches_service
from app.transactions.persistence import transactions_persistence
from app.wire.setup import (
    BackfillRequest,
    BackfillResponse,
    ConnectRequest,
    ConnectResponse,
    HealthResponse,
    RefreshResponse,
    StatusResponse,
)

router = APIRouter(tags=["setup"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", source=settings.source, database=str(settings.database_path))


@router.get("/status", response_model=StatusResponse)
def get_status(connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]) -> StatusResponse:
    stored_credentials = credentials.read_credentials()
    last_fetch = fetches_persistence.get_last_fetch(connection)
    guard = fetches_service.refresh_guard(connection)

    return StatusResponse(
        connected=stored_credentials is not None,
        source=settings.source,
        credential_claimed_at=stored_credentials.claimed_at if stored_credentials is not None else None,
        account_count=accounts_persistence.count_accounts(connection),
        transaction_count=transactions_persistence.count_transactions(connection),
        last_fetch_status=last_fetch.status if last_fetch is not None else None,
        last_fetched_at=last_fetch.fetched_at if last_fetch is not None else None,
        last_fetch_error_code=last_fetch.error_code if last_fetch is not None else None,
        refresh_allowed=guard.allowed,
        next_refresh_allowed_at=guard.next_allowed_at,
        refresh_min_interval_hours=settings.refresh_min_interval_hours,
    )


@router.post("/connect", response_model=ConnectResponse)
def post_connect(
    request: ConnectRequest, connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]
) -> ConnectResponse:
    if credentials.read_credentials() is not None and not request.replace:
        raise HTTPException(status_code=409, detail=errors.ALREADY_CONNECTED_MESSAGE)

    source = simplefin.get_account_source()
    access_url = source.claim(request.setup_token)
    stored_credentials = credentials.write_credentials(access_url)
    backfill = fetches_service.run_backfill(connection, source, stored_credentials.access_url)

    return ConnectResponse(
        connected=True,
        account_count=accounts_persistence.count_accounts(connection),
        backfill_windows=len(backfill.windows),
        transactions_stored=backfill.transactions_stored,
    )


@router.post("/refresh", response_model=RefreshResponse, responses={429: {"description": "Refresh guard is active"}})
def post_refresh(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> RefreshResponse | JSONResponse:
    stored_credentials = credentials.read_credentials()

    if stored_credentials is None:
        raise errors.not_connected_error()

    guard = fetches_service.refresh_guard(connection)

    if not guard.allowed:
        message = f"Refresh is not allowed yet. Next refresh allowed at {guard.next_allowed_at}."

        # A hand-built body is not aliased by ApiModel, so it spells the camelCase keys itself.
        return JSONResponse(
            status_code=429,
            content={
                "detail": message,
                "refreshAllowed": False,
                "nextRefreshAllowedAt": guard.next_allowed_at,
            },
        )

    source = simplefin.get_account_source()
    result = fetches_service.run_refresh(connection, source, stored_credentials.access_url)
    next_guard = fetches_service.refresh_guard(connection)

    return RefreshResponse(
        fetched=True,
        account_count=accounts_persistence.count_accounts(connection),
        transactions_stored=result.transactions_stored,
        fetched_at=result.fetched_at,
        refresh_allowed=next_guard.allowed,
        next_refresh_allowed_at=next_guard.next_allowed_at,
    )


@router.post("/backfill", response_model=BackfillResponse)
def post_backfill(
    request: BackfillRequest, connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]
) -> BackfillResponse:
    stored_credentials = credentials.read_credentials()

    if stored_credentials is None:
        raise errors.not_connected_error()

    source = simplefin.get_account_source()
    backfill = fetches_service.run_backfill(connection, source, stored_credentials.access_url, request.months)

    return BackfillResponse(windows=len(backfill.windows), transactions_stored=backfill.transactions_stored)
