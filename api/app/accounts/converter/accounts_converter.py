"""Account rows into wire models, field by field, with no I/O."""

from collections.abc import Sequence

from app.accounts.api.accounts_api import AccountResponse
from app.accounts.model.accounts_model import AccountRow


def to_account(row: AccountRow) -> AccountResponse:
    return AccountResponse(
        connection_id=row.connection_id,
        account_id=row.account_id,
        connection_name=row.connection_name,
        name=row.name,
        currency=row.currency,
        balance_cents=row.balance_cents,
        available_balance_cents=row.available_balance_cents,
        balance_date=row.balance_date,
        include_in_cash=row.include_in_cash,
    )


def to_accounts(rows: Sequence[AccountRow]) -> list[AccountResponse]:
    return [to_account(row) for row in rows]
