"""Every SQL statement about `data_fetches`, the log of what each fetch returned.

One function, one statement, and no decisions: whether a fetch is recent enough to stop another
one is policy, and it lives in `fetches_service`.
"""

import sqlite3

from app.fetches.model.fetches_model import FetchRecord, FetchWindow

INSERT_FETCH_SQL = """
INSERT INTO data_fetches (
    connection_id, window_start, window_end, fetched_at, status, transaction_count, error_code, error_message
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_LAST_FETCH_SQL = "SELECT fetched_at, status, error_code FROM data_fetches ORDER BY id DESC LIMIT 1"

SELECT_LAST_SUCCESSFUL_FETCH_SQL = "SELECT max(fetched_at) AS fetched_at FROM data_fetches WHERE status = 'ok'"


def insert_fetch(
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


def get_last_fetch(connection: sqlite3.Connection) -> FetchRecord | None:
    row = connection.execute(SELECT_LAST_FETCH_SQL).fetchone()

    return None if row is None else FetchRecord.from_row(row)


def get_last_successful_fetch_at(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(SELECT_LAST_SUCCESSFUL_FETCH_SQL).fetchone()
    fetched_at = None if row is None else row["fetched_at"]

    return None if fetched_at is None else str(fetched_at)
