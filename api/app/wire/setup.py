"""The setup and connection endpoints: health, status, connect, refresh, backfill."""

from pydantic import Field

from app.wire.base import ApiModel


class HealthResponse(ApiModel):
    status: str
    source: str
    database: str


class ConnectRequest(ApiModel):
    setup_token: str
    replace: bool = False


class ConnectResponse(ApiModel):
    connected: bool
    account_count: int
    backfill_windows: int
    transactions_stored: int


class StatusResponse(ApiModel):
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


class RefreshResponse(ApiModel):
    fetched: bool
    account_count: int
    transactions_stored: int
    fetched_at: str
    refresh_allowed: bool
    next_refresh_allowed_at: str | None


class BackfillRequest(ApiModel):
    months: int = Field(default=12, ge=1, le=36)


class BackfillResponse(ApiModel):
    windows: int
    transactions_stored: int
