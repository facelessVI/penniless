"""What the connection endpoints report, with the fetch vocabulary kept typed rather than flattened."""

from dataclasses import dataclass

from app.fetches.model.fetches_model import FetchRecord, RefreshGuard


@dataclass(frozen=True)
class StatusReport:
    connected: bool
    credential_claimed_at: str | None
    account_count: int
    transaction_count: int
    last_fetch: FetchRecord | None
    refresh_guard: RefreshGuard


@dataclass(frozen=True)
class ConnectReport:
    account_count: int
    backfill_windows: int
    transactions_stored: int


@dataclass(frozen=True)
class RefreshReport:
    fetched_at: str
    account_count: int
    transactions_stored: int
    refresh_guard: RefreshGuard


@dataclass(frozen=True)
class BackfillReport:
    windows: int
    transactions_stored: int
