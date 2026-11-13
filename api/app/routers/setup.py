"""Setup endpoints: health, connection status, connect, refresh, backfill."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app import credentials, db, errors, ingest, simplefin
from app.config import settings
from app.schemas import (
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
    last_fetch = ingest.last_fetch(connection)
    guard = ingest.refresh_guard(connection)

    return StatusResponse(
        connected=stored_credentials is not None,
        source=settings.source,
        credential_claimed_at=stored_credentials.claimed_at if stored_credentials is not None else None,
        account_count=ingest.count_rows(connection, "accounts"),
        transaction_count=ingest.count_rows(connection, "transactions"),
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

    try:
        access_url = source.claim(request.setup_token)
    except errors.SimpleFinError as error:
        raise error.to_http_exception() from error

    stored_credentials = credentials.write_credentials(access_url)

    try:
        backfill = ingest.run_backfill(connection, source, stored_credentials.access_url)
    except errors.SimpleFinError as error:
        raise error.to_http_exception() from error

    return ConnectResponse(
        connected=True,
        account_count=ingest.count_rows(connection, "accounts"),
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

    guard = ingest.refresh_guard(connection)

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

    try:
        result = ingest.run_refresh(connection, source, stored_credentials.access_url)
    except errors.SimpleFinError as error:
        raise error.to_http_exception() from error

    next_guard = ingest.refresh_guard(connection)

    return RefreshResponse(
        fetched=True,
        account_count=ingest.count_rows(connection, "accounts"),
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

    try:
        backfill = ingest.run_backfill(connection, source, stored_credentials.access_url, request.months)
    except errors.SimpleFinError as error:
        raise error.to_http_exception() from error

    return BackfillResponse(windows=len(backfill.windows), transactions_stored=backfill.transactions_stored)
