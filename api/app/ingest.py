"""Window planning, composite-key upserts, fetch bookkeeping, and the refresh guard."""

import math
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from app.categorize import CategoryRules, load_rules
from app.config import settings
from app.db import now_iso, parse_cents
from app.errors import SimpleFinError, sanitize_message
from app.schemas import SimpleFinAccount, SimpleFinConnection
from app.schemas import SimpleFinError as SimpleFinErrorEntry
from app.simplefin import AccountSource

BACKFILL_MONTHS = 12
DAYS_PER_MONTH = 30.44

# The Bridge counts a requested range inclusive of both of its dates and caps a request at 90
# days, so windows are requested one day short of that: 89 days here is 90 days inclusive, which
# leaves no headroom for the cap to trim an answer. Its 45-day figure is a recommendation, and
# overrunning it produces a `gen.api` advisory rather than a failure (see ADVISORY_ERROR_CODES).
WINDOW_LENGTH_DAYS = 89
WINDOW_OVERLAP_DAYS = 5

# `gen.api` is the protocol's developer-facing namespace: "Error in how the API is being used. This
# is meant for the developer and not for the user." Every other code (`con.*`, `act.*`, `gen.auth`)
# is a failure the user needs to see, because accounts or transactions may be missing.
ADVISORY_ERROR_CODES = frozenset({"gen.api"})
# SimpleFIN reports no account type. When the Bridge does supply `extra.type`, only these are
# demoted out of the cash total; anything unknown or missing stays in, which keeps the total
# conservative until it is corrected with the UI toggle.
NON_CASH_ACCOUNT_TYPES = {
    "credit",
    "credit card",
    "loan",
    "mortgage",
    "student loan",
    "auto loan",
    "investment",
    "brokerage",
    "retirement",
}

UPSERT_ACCOUNT_SQL = """
INSERT INTO accounts (
    connection_id, account_id, connection_name, name, currency, balance_cents,
    available_balance_cents, balance_date, include_in_cash, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (connection_id, account_id) DO UPDATE SET
    connection_name = excluded.connection_name,
    name = excluded.name,
    currency = excluded.currency,
    balance_cents = excluded.balance_cents,
    available_balance_cents = excluded.available_balance_cents,
    balance_date = excluded.balance_date,
    updated_at = excluded.updated_at
"""

UPSERT_ACCOUNT_BALANCE_SQL = """
INSERT INTO account_balances (
    connection_id, account_id, balance_date, balance_cents, available_balance_cents, recorded_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (connection_id, account_id, balance_date) DO UPDATE SET
    balance_cents = excluded.balance_cents,
    available_balance_cents = excluded.available_balance_cents,
    recorded_at = excluded.recorded_at
"""

UPSERT_TRANSACTION_SQL = """
INSERT INTO transactions (
    connection_id, account_id, transaction_id, posted_at, posted_date, transacted_at,
    description, amount_cents, category, is_transfer, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (connection_id, account_id, transaction_id) DO UPDATE SET
    posted_at = excluded.posted_at,
    posted_date = excluded.posted_date,
    transacted_at = excluded.transacted_at,
    description = excluded.description,
    amount_cents = excluded.amount_cents,
    category = excluded.category,
    is_transfer = excluded.is_transfer,
    updated_at = excluded.updated_at
"""

INSERT_FETCH_SQL = """
INSERT INTO data_fetches (
    connection_id, window_start, window_end, fetched_at, status, transaction_count, error_code, error_message
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class FetchWindow:
    start_date: date
    end_date: date

    @property
    def start_epoch(self) -> int:
        return day_start_epoch(self.start_date)

    @property
    def end_epoch(self) -> int:
        return day_start_epoch(self.end_date)

    @property
    def start_iso(self) -> str:
        return self.start_date.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end_date.isoformat()


@dataclass(frozen=True)
class FetchRecord:
    fetched_at: str
    status: str
    error_code: str | None


@dataclass(frozen=True)
class RefreshGuard:
    allowed: bool
    next_allowed_at: str | None


@dataclass(frozen=True)
class IngestResult:
    window: FetchWindow
    fetched_at: str
    transaction_count: int
    transactions_stored: int


@dataclass(frozen=True)
class BackfillResult:
    windows: list[FetchWindow]
    transactions_stored: int


def day_start_epoch(day: date) -> int:
    """Midnight local time for a calendar date, which is how SimpleFIN windows are read here."""
    return int(datetime.combine(day, time.min).timestamp())


def local_date(epoch_seconds: int) -> date:
    return datetime.fromtimestamp(epoch_seconds).date()


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


def classify_errors(errors: list[SimpleFinErrorEntry]) -> tuple[list[SimpleFinErrorEntry], list[SimpleFinErrorEntry]]:
    """Split an Account Set's errlist into developer-only advisories and user-facing failures."""
    advisories = [error for error in errors if error.code in ADVISORY_ERROR_CODES]
    failures = [error for error in errors if error.code not in ADVISORY_ERROR_CODES]

    return advisories, failures


def resolve_connection(account: SimpleFinAccount, connections_by_id: dict[str, SimpleFinConnection]) -> tuple[str, str]:
    if account.conn_id:
        connection = connections_by_id.get(account.conn_id)
        name = (connection.name if connection is not None else None) or account.conn_name or account.conn_id

        return account.conn_id, name

    # Protocol v1 nests the institution on the account and has no connection ids at all.
    if account.org is not None:
        identifier = account.org.sfin_url or account.org.domain

        if identifier:
            return identifier, account.org.name or identifier

    raise SimpleFinError(f"SimpleFIN account {account.id} carries no connection identifier; refusing to guess one.")


def infer_include_in_cash(extra: dict[str, Any]) -> int:
    account_type = extra.get("type")

    if isinstance(account_type, str) and account_type.strip().lower() in NON_CASH_ACCOUNT_TYPES:
        return 0

    return 1


def is_storable(transaction_posted: int | None, pending: bool) -> bool:
    """Pending rows never appear in v0 responses, and a 0 posted date means "not posted yet"."""
    return not pending and transaction_posted is not None and transaction_posted > 0


def count_rows(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f"SELECT count(*) AS total FROM {table}").fetchone()

    return int(row["total"])


def last_fetch(connection: sqlite3.Connection) -> FetchRecord | None:
    row = connection.execute(
        "SELECT fetched_at, status, error_code FROM data_fetches ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if row is None:
        return None

    return FetchRecord(fetched_at=row["fetched_at"], status=row["status"], error_code=row["error_code"])


def refresh_guard(connection: sqlite3.Connection, now: datetime | None = None) -> RefreshGuard:
    row = connection.execute("SELECT max(fetched_at) AS fetched_at FROM data_fetches WHERE status = 'ok'").fetchone()
    last_successful_fetch = row["fetched_at"] if row is not None else None

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
    # Validate the rules first: a broken categories file must not cost a fetch.
    rules = load_rules()
    fetched_at = now_iso()

    try:
        account_set = source.fetch(access_url, window.start_epoch, window.end_epoch)
    except SimpleFinError as error:
        record_fetch(
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
    connections_by_id = {item.conn_id: item for item in account_set.connections}
    connection_ids: set[str] = set()
    transaction_count = 0

    with connection:
        for account in account_set.accounts:
            connection_id, connection_name = resolve_connection(account, connections_by_id)
            connection_ids.add(connection_id)
            transaction_count += upsert_account(connection, account, connection_id, connection_name, fetched_at, rules)

        record_fetch(
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
        transactions_stored=count_rows(connection, "transactions"),
    )


def upsert_account(
    connection: sqlite3.Connection,
    account: SimpleFinAccount,
    connection_id: str,
    connection_name: str,
    fetched_at: str,
    rules: CategoryRules,
) -> int:
    balance_cents = parse_cents(account.balance)

    if balance_cents is None:
        raise SimpleFinError(f"SimpleFIN account {account.id} reported no balance.")

    balance_date = local_date(account.balance_date).isoformat()
    available_balance_cents = parse_cents(account.available_balance)

    connection.execute(
        UPSERT_ACCOUNT_SQL,
        (
            connection_id,
            account.id,
            connection_name,
            account.name,
            account.currency,
            balance_cents,
            available_balance_cents,
            balance_date,
            infer_include_in_cash(account.extra),
            fetched_at,
            fetched_at,
        ),
    )
    connection.execute(
        UPSERT_ACCOUNT_BALANCE_SQL,
        (connection_id, account.id, balance_date, balance_cents, available_balance_cents, fetched_at),
    )

    stored = 0

    for transaction in account.transactions:
        posted_epoch = transaction.posted

        if posted_epoch is None or not is_storable(posted_epoch, transaction.pending):
            continue

        amount_cents = parse_cents(transaction.amount)

        if amount_cents is None:
            raise SimpleFinError(f"SimpleFIN transaction {transaction.id} reported no amount.")

        category, is_transfer = rules.classify(transaction.description)

        posted_date = local_date(posted_epoch).isoformat()
        transacted_at = local_date(transaction.transacted_at).isoformat() if transaction.transacted_at else None

        connection.execute(
            UPSERT_TRANSACTION_SQL,
            (
                connection_id,
                account.id,
                transaction.id,
                datetime.fromtimestamp(posted_epoch, UTC).isoformat(timespec="seconds"),
                posted_date,
                transacted_at,
                transaction.description,
                amount_cents,
                category,
                int(is_transfer),
                fetched_at,
                fetched_at,
            ),
        )
        stored += 1

    return stored


def record_fetch(
    connection: sqlite3.Connection,
    window: FetchWindow,
    fetched_at: str,
    connection_id: str | None,
    status: str,
    transaction_count: int,
    error_code: str | None,
    error_message: str | None,
) -> None:
    connection.execute(
        INSERT_FETCH_SQL,
        (
            connection_id,
            window.start_iso,
            window.end_iso,
            fetched_at,
            status,
            transaction_count,
            error_code,
            error_message,
        ),
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

    return BackfillResult(windows=windows, transactions_stored=count_rows(connection, "transactions"))


def run_refresh(connection: sqlite3.Connection, source: AccountSource, access_url: str) -> IngestResult:
    return ingest_window(connection, source, access_url, plan_refresh_window())
