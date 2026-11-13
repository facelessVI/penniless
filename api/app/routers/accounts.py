"""Account list and the cash-total toggle."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app import converters, ledger
from app.common import db
from app.wire.accounts import AccountResponse, AccountUpdateRequest

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]) -> list[AccountResponse]:
    return converters.to_accounts(ledger.get_accounts(connection))


@router.patch("/accounts/{connection_id}/{account_id}", response_model=AccountResponse)
def update_account(
    connection_id: str,
    account_id: str,
    request: AccountUpdateRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> AccountResponse:
    row = ledger.set_account_included_in_cash(connection, connection_id, account_id, request.include_in_cash)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown account {account_id} on connection {connection_id}.",
        )

    return converters.to_account(row)
