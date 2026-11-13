"""Account list and the cash-total toggle."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.accounts.api.accounts_api import AccountResponse, AccountUpdateRequest
from app.accounts.converter import accounts_converter as converter
from app.accounts.persistence import accounts_persistence as persistence
from app.common import db

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]) -> list[AccountResponse]:
    return converter.to_accounts(persistence.get_accounts(connection))


@router.patch("/accounts/{connection_id}/{account_id}", response_model=AccountResponse)
def update_account(
    connection_id: str,
    account_id: str,
    request: AccountUpdateRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> AccountResponse:
    row = persistence.set_account_included_in_cash(connection, connection_id, account_id, request.include_in_cash)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown account {account_id} on connection {connection_id}.",
        )

    return converter.to_account(row)
