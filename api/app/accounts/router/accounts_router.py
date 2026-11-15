"""The account list and the one endpoint that edits an account's metadata."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app.accounts.api.accounts_api import AccountResponse, AccountUpdateRequest
from app.accounts.converter import accounts_converter as converter
from app.accounts.model.accounts_model import AccountChanges
from app.accounts.service import accounts_service as service
from app.common import db

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]) -> list[AccountResponse]:
    return converter.to_accounts(service.list_accounts(connection))


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
        labels=None if request.labels is None else tuple(request.labels),
    )

    return converter.to_account(service.update_account(connection, connection_id, account_id, changes))
