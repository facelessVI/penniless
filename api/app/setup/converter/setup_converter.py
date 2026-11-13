"""Setup reports into wire models, and the two process constants they carry.

`source` and the refresh interval come from `settings` here because they are fixed for the
life of the process: they are not state a caller passes in, and every response that needs
them needs the same value.
"""

from app.common.config import settings
from app.setup.api.setup_api import (
    BackfillResponse,
    ConnectResponse,
    HealthResponse,
    RefreshResponse,
    StatusResponse,
)
from app.setup.model.setup_model import (
    BackfillReport,
    ConnectReport,
    RefreshReport,
    StatusReport,
)


def to_health() -> HealthResponse:
    return HealthResponse(status="ok", source=settings.source, database=str(settings.database_path))


def to_status(report: StatusReport) -> StatusResponse:
    last_fetch = report.last_fetch

    return StatusResponse(
        connected=report.connected,
        source=settings.source,
        credential_claimed_at=report.credential_claimed_at,
        account_count=report.account_count,
        transaction_count=report.transaction_count,
        last_fetch_status=last_fetch.status if last_fetch is not None else None,
        last_fetched_at=last_fetch.fetched_at if last_fetch is not None else None,
        last_fetch_error_code=last_fetch.error_code if last_fetch is not None else None,
        refresh_allowed=report.refresh_guard.allowed,
        next_refresh_allowed_at=report.refresh_guard.next_allowed_at,
        refresh_min_interval_hours=settings.refresh_min_interval_hours,
    )


def to_connect(report: ConnectReport) -> ConnectResponse:
    return ConnectResponse(
        connected=True,
        account_count=report.account_count,
        backfill_windows=report.backfill_windows,
        transactions_stored=report.transactions_stored,
    )


def to_refresh(report: RefreshReport) -> RefreshResponse:
    return RefreshResponse(
        fetched=True,
        account_count=report.account_count,
        transactions_stored=report.transactions_stored,
        fetched_at=report.fetched_at,
        refresh_allowed=report.refresh_guard.allowed,
        next_refresh_allowed_at=report.refresh_guard.next_allowed_at,
    )


def to_backfill(report: BackfillReport) -> BackfillResponse:
    return BackfillResponse(windows=report.windows, transactions_stored=report.transactions_stored)
