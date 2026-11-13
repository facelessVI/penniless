"""Setup endpoints: health, connection status, connect, refresh, backfill."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app.common import db
from app.setup.api.setup_api import (
    BackfillRequest,
    BackfillResponse,
    ConnectRequest,
    ConnectResponse,
    HealthResponse,
    RefreshResponse,
    StatusResponse,
)
from app.setup.converter import setup_converter as converter
from app.setup.service import setup_service as service

router = APIRouter(tags=["setup"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return converter.to_health()


@router.get("/status", response_model=StatusResponse)
def get_status(connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]) -> StatusResponse:
    return converter.to_status(service.get_status(connection))


@router.post("/connect", response_model=ConnectResponse)
def post_connect(
    request: ConnectRequest, connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]
) -> ConnectResponse:
    return converter.to_connect(service.connect(connection, request.setup_token, request.replace))


@router.post("/refresh", response_model=RefreshResponse, responses={429: {"description": "Refresh guard is active"}})
def post_refresh(
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> RefreshResponse:
    return converter.to_refresh(service.refresh(connection))


@router.post("/backfill", response_model=BackfillResponse)
def post_backfill(
    request: BackfillRequest, connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]
) -> BackfillResponse:
    return converter.to_backfill(service.backfill(connection, request.months))
