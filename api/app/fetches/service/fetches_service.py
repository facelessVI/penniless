"""Pulling windows from SimpleFIN and recording what each one returned.

A window is the unit of spend: every call costs one of the day's 24, so the plan, the error
classification, and the quota guard are all decided here and nowhere else. The account and
transaction halves of the write live with their own entities; this module sequences them.
"""

import math
import sqlite3
from datetime import UTC, date, datetime, timedelta

from app.accounts.service import accounts_service
from app.categories.service.categories_service import get_category_rules
from app.common.config import settings
from app.common.db import now_iso
from app.common.errors import SimpleFinError, sanitize_message
from app.common.simplefin import AccountSource
from app.common.simplefin_api import SimpleFinConnection
from app.common.simplefin_api import SimpleFinError as SimpleFinErrorEntry
from app.fetches.constants.fetches_constants import (
    ADVISORY_ERROR_CODES,
    BACKFILL_MONTHS,
    DAYS_PER_MONTH,
    WINDOW_LENGTH_DAYS,
    WINDOW_OVERLAP_DAYS,
)
from app.fetches.model.fetches_model import BackfillResult, FetchWindow, IngestResult, RefreshGuard
from app.fetches.persistence import fetches_persistence as persistence
from app.transactions.persistence import transactions_persistence
from app.transactions.service import transactions_service


def plan_backfill_windows(months: int = BACKFILL_MONTHS, today: date | None = None) -> list[FetchWindow]:
    """Oldest first, covering `months` of calendar time: `WINDOW_LENGTH_DAYS` per fetch, overlapping."""
    reference = today or date.today()
    step = timedelta(days=WINDOW_LENGTH_DAYS - WINDOW_OVERLAP_DAYS)
    length = timedelta(days=WINDOW_LENGTH_DAYS)
    target = timedelta(days=months * DAYS_PER_MONTH)
    newest_end = reference + timedelta(days=1)
    newest_start = newest_end - length

    # The newest window covers `length` days and every older one adds another `step`, so derive the
    # count from the span that has to be covered instead of rounding months into window lengths.
    window_count = max(1, math.ceil((target - length) / step) + 1)

    windows: list[FetchWindow] = []
    for index in range(window_count):
        start = newest_start - step * (window_count - 1 - index)
        windows.append(FetchWindow(start_date=start, end_date=start + length))

    return windows


def plan_refresh_window(today: date | None = None) -> FetchWindow:
    """One short window covering the backfill's overlap plus today."""
    reference = today or date.today()
    end = reference + timedelta(days=1)

    return FetchWindow(start_date=end - timedelta(days=WINDOW_OVERLAP_DAYS), end_date=end)


def classify_errors(reported: list[SimpleFinErrorEntry]) -> tuple[list[SimpleFinErrorEntry], list[SimpleFinErrorEntry]]:
    """Split an Account Set's errlist into developer-only advisories and user-facing failures."""
    advisories = [error for error in reported if error.code in ADVISORY_ERROR_CODES]
    failures = [error for error in reported if error.code not in ADVISORY_ERROR_CODES]

    return advisories, failures


def refresh_guard(connection: sqlite3.Connection, now: datetime | None = None) -> RefreshGuard:
    """Whether the quota allows another fetch yet, and when it would."""
    last_successful_fetch = persistence.get_last_successful_fetch_at(connection)

    if not last_successful_fetch:
        return RefreshGuard(allowed=True, next_allowed_at=None)

    next_allowed = datetime.fromisoformat(last_successful_fetch) + timedelta(hours=settings.refresh_min_interval_hours)
    current_time = now or datetime.now(UTC)

    if current_time >= next_allowed:
        return RefreshGuard(allowed=True, next_allowed_at=None)

    return RefreshGuard(allowed=False, next_allowed_at=next_allowed.isoformat(timespec="seconds"))


def ingest_window(
    connection: sqlite3.Connection, source: AccountSource, access_url: str, window: FetchWindow
) -> IngestResult:
    # Validate the categories first: broken category data must not cost a fetch.
    rules = get_category_rules(connection)
    fetched_at = now_iso()

    try:
        account_set = source.fetch(access_url, window.start_epoch, window.end_epoch)
    except SimpleFinError as error:
        persistence.insert_fetch(
            connection,
            window,
            fetched_at=fetched_at,
            connection_id=None,
            status="error",
            transaction_count=0,
            error_code=error.error_code,
            error_message=error.message,
        )
        connection.commit()
        raise

    advisories, failures = classify_errors(account_set.errlist)
    reported_errors = failures or advisories
    connections_by_id: dict[str, SimpleFinConnection] = {item.conn_id: item for item in account_set.connections}
    connection_ids: set[str] = set()
    transaction_count = 0

    with connection:
        for account in account_set.accounts:
            connection_id, connection_name = accounts_service.resolve_connection(account, connections_by_id)
            connection_ids.add(connection_id)
            accounts_service.upsert_account(connection, account, connection_id, connection_name, fetched_at)
            transaction_count += transactions_service.upsert_transactions(
                connection, account, connection_id, fetched_at, rules
            )

        persistence.insert_fetch(
            connection,
            window,
            fetched_at=fetched_at,
            connection_id=next(iter(connection_ids)) if len(connection_ids) == 1 else None,
            # `status` answers "is this window's data usable", not "did the Bridge stay silent": a
            # fetch that stored its accounts and transactions is `ok` even when the response carried
            # an advisory. `refresh_guard` reads this column, so the distinction sets the quota guard.
            status="ok" if not failures else "error",
            transaction_count=transaction_count,
            error_code=",".join(sorted({item.code for item in reported_errors})) or None,
            error_message=sanitize_message("; ".join(item.msg for item in reported_errors)) or None,
        )

    return IngestResult(
        window=window,
        fetched_at=fetched_at,
        transaction_count=transaction_count,
        transactions_stored=transactions_persistence.count_transactions(connection),
    )


def run_backfill(
    connection: sqlite3.Connection,
    source: AccountSource,
    access_url: str,
    months: int = BACKFILL_MONTHS,
) -> BackfillResult:
    windows = plan_backfill_windows(months)

    for window in windows:
        ingest_window(connection, source, access_url, window)

    return BackfillResult(windows=windows, transactions_stored=transactions_persistence.count_transactions(connection))


def run_refresh(connection: sqlite3.Connection, source: AccountSource, access_url: str) -> IngestResult:
    return ingest_window(connection, source, access_url, plan_refresh_window())
