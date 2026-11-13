"""Regression tests for the pure fetch policies: error classification and window planning.

No network, no fixture files, and no on-disk database: the stub source returns a hand-built Account
Set and every database lives in memory.
"""

import sqlite3
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from app import ingest, migrations
from app.schemas import (
    SimpleFinAccount,
    SimpleFinAccountSet,
    SimpleFinConnection,
    SimpleFinError,
    SimpleFinTransaction,
)

BALANCE_EPOCH = 1_790_000_000
POSTED_EPOCH = 1_789_000_000
WINDOW = ingest.FetchWindow(start_date=date(2026, 11, 6), end_date=date(2026, 11, 11))
ADVISORY_MESSAGE = "Requested date range exceeds recommended range of 45 days."
CONNECTION_MESSAGE = "Authentication failed for Stub Bank"


class StubAccountSource:
    """An `AccountSource` that returns a canned Account Set and never opens a socket."""

    def __init__(self, account_set: SimpleFinAccountSet) -> None:
        self.account_set = account_set

    def claim(self, setup_token: str) -> str:
        raise NotImplementedError

    def fetch(self, access_url: str, start_epoch: int, end_epoch: int) -> SimpleFinAccountSet:
        return self.account_set


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrations.run_migrations(connection)

    return connection


def build_account_set(errors: Sequence[SimpleFinError]) -> SimpleFinAccountSet:
    connection = SimpleFinConnection(conn_id="CON-1", name="Stub Bank")
    transaction = SimpleFinTransaction(id="TX-1", posted=POSTED_EPOCH, amount="-12.34", description="STUB PURCHASE")
    # Validated from the wire shape: `balance-date` is an alias, and the alias is what the Bridge sends.
    account = SimpleFinAccount.model_validate(
        {
            "id": "ACT-1",
            "name": "Everyday Checking",
            "conn_id": "CON-1",
            "currency": "USD",
            "balance": "100.00",
            "balance-date": BALANCE_EPOCH,
            "transactions": [transaction],
        }
    )

    return SimpleFinAccountSet(errlist=list(errors), connections=[connection], accounts=[account])


def newest_fetch_row(connection: sqlite3.Connection) -> sqlite3.Row:
    row = connection.execute(
        "SELECT status, transaction_count, error_code, error_message FROM data_fetches ORDER BY id DESC LIMIT 1"
    ).fetchone()

    assert row is not None

    return row


def guard_after(connection: sqlite3.Connection, fetched_at: str, minutes: int) -> ingest.RefreshGuard:
    return ingest.refresh_guard(connection, now=datetime.fromisoformat(fetched_at) + timedelta(minutes=minutes))


def test_gen_api_advisory_records_a_successful_fetch() -> None:
    """A developer-only advisory must not mark stored data as stale, and must arm the refresh guard."""
    connection = make_connection()
    account_source = StubAccountSource(build_account_set([SimpleFinError(code="gen.api", msg=ADVISORY_MESSAGE)]))

    result = ingest.ingest_window(connection, account_source, "https://unused.invalid", WINDOW)

    row = newest_fetch_row(connection)
    assert row["status"] == "ok"
    assert row["error_code"] == "gen.api"
    assert row["transaction_count"] == 1
    assert "45 days" in row["error_message"]
    assert ingest.count_rows(connection, "accounts") == 1
    assert ingest.count_rows(connection, "transactions") == 1
    assert guard_after(connection, result.fetched_at, minutes=1).allowed is False


def test_connection_error_records_a_failed_fetch() -> None:
    """A user-facing failure still fails the fetch, keeps its code, and leaves the guard open."""
    connection = make_connection()
    account_source = StubAccountSource(
        build_account_set([SimpleFinError(code="con.auth", msg=CONNECTION_MESSAGE, conn_id="CON-1")])
    )

    result = ingest.ingest_window(connection, account_source, "https://unused.invalid", WINDOW)

    row = newest_fetch_row(connection)
    assert row["status"] == "error"
    assert row["error_code"] == "con.auth"
    assert CONNECTION_MESSAGE in row["error_message"]
    assert guard_after(connection, result.fetched_at, minutes=1).allowed is True


def test_backfill_windows_cover_twelve_months_without_exceeding_the_cap() -> None:
    """Twelve months of history, oldest first, each window safely inside the Bridge's 90-day cap."""
    today = date(2026, 11, 10)

    windows = ingest.plan_backfill_windows(12, today)

    assert windows[-1].end_date == today + timedelta(days=1)
    assert (windows[-1].end_date - windows[0].start_date).days >= 365

    for window in windows:
        assert (window.end_date - window.start_date).days == ingest.WINDOW_LENGTH_DAYS
        assert (window.end_date - window.start_date).days <= 89

    for older, newer in zip(windows, windows[1:], strict=False):
        assert newer.start_date - older.start_date == timedelta(
            days=ingest.WINDOW_LENGTH_DAYS - ingest.WINDOW_OVERLAP_DAYS
        )

    one_month_end = today + timedelta(days=1)
    one_month_start = one_month_end - timedelta(days=ingest.WINDOW_LENGTH_DAYS)
    assert ingest.plan_backfill_windows(1, today) == [
        ingest.FetchWindow(start_date=one_month_start, end_date=one_month_end)
    ]
