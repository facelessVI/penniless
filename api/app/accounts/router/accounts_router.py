"""The account list, the two writes that change it, and the endpoint that edits one account."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app.accounts.api.accounts_api import AccountCreateRequest, AccountResponse, AccountUpdateRequest
from app.accounts.converter import accounts_converter as converter
from app.accounts.model.accounts_model import AccountChanges
from app.accounts.service import accounts_service as service
from app.common import db

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]) -> list[AccountResponse]:
    return converter.to_accounts(service.list_accounts(connection))


@router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(
    request: AccountCreateRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> AccountResponse:
    created = service.create_manual_account(
        connection,
        request.name,
        request.balance_cents,
        request.description,
        () if request.labels is None else tuple(request.labels),
    )

    return converter.to_account(created)


@router.patch("/accounts/{connection_id}/{account_id}", response_model=AccountResponse)
def update_account(
    connection_id: str,
    account_id: str,
    request: AccountUpdateRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> AccountResponse:
    changes = AccountChanges(
        display_name=request.display_name,
        description=request.description,
        include_in_cash=request.include_in_cash,
        balance_cents=request.balance_cents,
        labels=None if request.labels is None else tuple(request.labels),
    )

    return converter.to_account(service.update_account(connection, connection_id, account_id, changes))


@router.delete("/accounts/{connection_id}/{account_id}", response_model=list[AccountResponse])
def delete_account(
    connection_id: str,
    account_id: str,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> list[AccountResponse]:
    return converter.to_accounts(service.delete_account(connection, connection_id, account_id))
