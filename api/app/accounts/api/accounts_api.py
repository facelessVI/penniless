"""The account list, the metadata a PATCH carries, and the account it answers with."""

from app.common.api_model import ApiModel


class AccountResponse(ApiModel):
    connection_id: str
    account_id: str
    connection_name: str
    name: str
    display_name: str | None
    description: str | None
    currency: str
    balance_cents: int
    available_balance_cents: int | None
    balance_date: str
    include_in_cash: bool
    labels: list[str]


class AccountUpdateRequest(ApiModel):
    display_name: str | None = None
    description: str | None = None
    include_in_cash: bool | None = None
    labels: list[str] | None = None
