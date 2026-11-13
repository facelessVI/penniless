"""The SimpleFIN payload we accept. Its names and casing are SimpleFIN's, so nothing here is aliased."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SimpleFinModel(BaseModel):
    """Unknown keys are ignored: upstream adding a field must never break a fetch."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class SimpleFinError(SimpleFinModel):
    code: str
    msg: str = ""
    conn_id: str | None = None
    account_id: str | None = None


class SimpleFinOrganization(SimpleFinModel):
    id: str | None = None
    name: str | None = None
    domain: str | None = None
    url: str | None = None
    sfin_url: str | None = Field(default=None, alias="sfin-url")


class SimpleFinConnection(SimpleFinModel):
    conn_id: str
    name: str
    org_id: str | None = None
    org_name: str | None = None
    org_url: str | None = None
    sfin_url: str | None = None


class SimpleFinTransaction(SimpleFinModel):
    id: str
    posted: int | None = None
    amount: str
    description: str = ""
    transacted_at: int | None = None
    pending: bool = False


class SimpleFinAccount(SimpleFinModel):
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


class SimpleFinAccountSet(SimpleFinModel):
    errlist: list[SimpleFinError] = []
    errors: list[str] = []
    connections: list[SimpleFinConnection] = []
    accounts: list[SimpleFinAccount] = []
