"""Account list and the cash-total toggle."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app.accounts.api.accounts_api import AccountResponse, AccountUpdateRequest
from app.accounts.converter import accounts_converter as converter
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
    return converter.to_account(
        service.set_account_included_in_cash(connection, connection_id, account_id, request.include_in_cash)
    )
