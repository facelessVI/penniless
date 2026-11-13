"""The account list and the cash-total toggle."""

from app.wire.base import ApiModel


class AccountResponse(ApiModel):
    connection_id: str
    account_id: str
    connection_name: str
    name: str
    currency: str
    balance_cents: int
    available_balance_cents: int | None
    balance_date: str
    include_in_cash: bool


class AccountUpdateRequest(ApiModel):
    include_in_cash: bool
