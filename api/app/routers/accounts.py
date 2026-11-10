"""Account list and the cash-total toggle."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.schemas import AccountResponse, AccountUpdateRequest

router = APIRouter(tags=["accounts"])

ACCOUNT_COLUMNS = """
    connection_id, account_id, connection_name, name, currency, balance_cents,
    available_balance_cents, balance_date, include_in_cash
"""

SELECT_ACCOUNTS_SQL = f"SELECT {ACCOUNT_COLUMNS} FROM accounts ORDER BY connection_name, name"

SELECT_ACCOUNT_SQL = f"SELECT {ACCOUNT_COLUMNS} FROM accounts WHERE connection_id = ? AND account_id = ?"

UPDATE_INCLUDE_IN_CASH_SQL = """
UPDATE accounts SET include_in_cash = ?, updated_at = ? WHERE connection_id = ? AND account_id = ?
"""


def to_account_response(row: sqlite3.Row) -> AccountResponse:
    return AccountResponse(
        connection_id=row["connection_id"],
        account_id=row["account_id"],
        connection_name=row["connection_name"],
        name=row["name"],
        currency=row["currency"],
        balance_cents=row["balance_cents"],
        available_balance_cents=row["available_balance_cents"],
        balance_date=row["balance_date"],
        include_in_cash=bool(row["include_in_cash"]),
    )


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(connection: Annotated[sqlite3.Connection, Depends(db.get_connection)]) -> list[AccountResponse]:
    return [to_account_response(row) for row in connection.execute(SELECT_ACCOUNTS_SQL)]


@router.patch("/accounts/{connection_id}/{account_id}", response_model=AccountResponse)
def update_account(
    connection_id: str,
    account_id: str,
    request: AccountUpdateRequest,
    connection: Annotated[sqlite3.Connection, Depends(db.get_connection)],
) -> AccountResponse:
    with connection:
        cursor = connection.execute(
            UPDATE_INCLUDE_IN_CASH_SQL,
            (int(request.include_in_cash), db.now_iso(), connection_id, account_id),
        )

    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown account {account_id} on connection {connection_id}.",
        )

    row = connection.execute(SELECT_ACCOUNT_SQL, (connection_id, account_id)).fetchone()

    return to_account_response(row)
