"""The account list, the two bodies a write carries, and the account they answer with."""

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
    source: int
    labels: list[str]


class AccountCreateRequest(ApiModel):
    """A cash account the user creates: the balance is theirs to set from the first save."""

    name: str
    balance_cents: int
    description: str | None = None
    labels: list[str] | None = None


class AccountUpdateRequest(ApiModel):
    display_name: str | None = None
    description: str | None = None
    include_in_cash: bool | None = None
    balance_cents: int | None = None
    labels: list[str] | None = None
