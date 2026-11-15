"""Accounts into wire models, field by field, with no I/O."""

from collections.abc import Sequence

from app.accounts.api.accounts_api import AccountResponse
from app.accounts.model.accounts_model import Account


def to_account(account: Account) -> AccountResponse:
    return AccountResponse(
        connection_id=account.connection_id,
        account_id=account.account_id,
        connection_name=account.connection_name,
        name=account.name,
        display_name=account.display_name,
        description=account.description,
        currency=account.currency,
        balance_cents=account.balance_cents,
        available_balance_cents=account.available_balance_cents,
        balance_date=account.balance_date,
        include_in_cash=account.include_in_cash,
    )


def to_accounts(accounts: Sequence[Account]) -> list[AccountResponse]:
    return [to_account(account) for account in accounts]
