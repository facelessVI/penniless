"""Wire models: the SimpleFIN payload we accept, and every response we return."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SimpleFinError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    msg: str = ""
    conn_id: str | None = None
    account_id: str | None = None


class SimpleFinOrganization(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = None
    name: str | None = None
    domain: str | None = None
    url: str | None = None
    sfin_url: str | None = Field(default=None, alias="sfin-url")


class SimpleFinConnection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    conn_id: str
    name: str
    org_id: str | None = None
    org_name: str | None = None
    org_url: str | None = None
    sfin_url: str | None = None


class SimpleFinTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    posted: int | None = None
    amount: str
    description: str = ""
    transacted_at: int | None = None
    pending: bool = False


class SimpleFinAccount(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    conn_id: str | None = None
    conn_name: str | None = None
    currency: str = "USD"
    balance: str
    available_balance: str | None = Field(default=None, alias="available-balance")
    balance_date: int = Field(alias="balance-date")
    transactions: list[SimpleFinTransaction] = []
    extra: dict[str, Any] = {}
    org: SimpleFinOrganization | None = None


class SimpleFinAccountSet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    errlist: list[SimpleFinError] = []
    errors: list[str] = []
    connections: list[SimpleFinConnection] = []
    accounts: list[SimpleFinAccount] = []


class HealthResponse(BaseModel):
    status: str
    source: str
    database: str


class ConnectRequest(BaseModel):
    setup_token: str
    replace: bool = False


class ConnectResponse(BaseModel):
    connected: bool
    account_count: int
    backfill_windows: int
    transactions_stored: int


class StatusResponse(BaseModel):
    connected: bool
    source: str
    credential_claimed_at: str | None
    account_count: int
    transaction_count: int
    last_fetch_status: str | None
    last_fetched_at: str | None
    last_fetch_error_code: str | None
    refresh_allowed: bool
    next_refresh_allowed_at: str | None
    refresh_min_interval_hours: float


class RefreshResponse(BaseModel):
    fetched: bool
    account_count: int
    transactions_stored: int
    fetched_at: str
    refresh_allowed: bool
    next_refresh_allowed_at: str | None


class BackfillRequest(BaseModel):
    months: int = Field(default=12, ge=1, le=36)


class BackfillResponse(BaseModel):
    windows: int
    transactions_stored: int


class AccountResponse(BaseModel):
    connection_id: str
    account_id: str
    connection_name: str
    name: str
    currency: str
    balance_cents: int
    available_balance_cents: int | None
    balance_date: str
    include_in_cash: bool


class AccountUpdateRequest(BaseModel):
    include_in_cash: bool


class SummaryResponse(BaseModel):
    start: str
    end: str
    total_in_cents: int
    total_out_cents: int
    net_cents: int
    cash_total_cents: int
    net_worth_cents: int
    transaction_count: int


class TransactionItem(BaseModel):
    connection_id: str
    account_id: str
    account_name: str
    transaction_id: str
    posted_date: str
    description: str
    category: str
    amount_cents: int


class TransactionListResponse(BaseModel):
    items: list[TransactionItem]
    total: int
    limit: int
    offset: int


class TransactionCategoryRequest(BaseModel):
    connection_id: str
    account_id: str
    transaction_id: str
    category: str


class TransactionCategoryResponse(BaseModel):
    description: str
    category: str
    updated: int


class CategoriesResponse(BaseModel):
    categories: list[str]
    uncategorized: str


class ApplyCategoriesResponse(BaseModel):
    updated: int
    uncategorized: int
