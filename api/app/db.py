"""SQLite connections: one per request, plus the rule snapshot the fixture reset carries over."""

import sqlite3
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings


def connect(database_path: Path | None = None) -> sqlite3.Connection:
    path = database_path if database_path is not None else settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)

    # FastAPI runs sync dependencies and sync endpoints on different threadpool threads, and the
    # connection crosses between them. Each request owns its connection and touches it from one
    # thread at a time, so disabling sqlite3's thread check is safe here.
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")

    return connection


def get_connection() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, closed when the response is done."""
    connection = connect()

    try:
        yield connection
    finally:
        connection.close()


def now_iso() -> str:
    """Timestamps land in SQLite as UTC; only calendar dates are local."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def read_rules_snapshot(database_path: Path) -> list[tuple[str, str, str]]:
    """The rules already learned in a fixture database, read before its file is deleted.

    Rules are the one thing a fixture reset keeps: re-teaching every merchant on every restart would
    make the dev loop useless. A database from before the rules table existed has none, and one from
    before migration 004 has no `match_type` column: its rules were all exact, so they restore as
    exact rather than being dropped.
    """
    if not database_path.exists():
        return []

    connection = sqlite3.connect(database_path)

    try:
        has_rules_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'rules'"
        ).fetchone()

        if has_rules_table is None:
            return []

        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info('rules')")}

        if "match_type" in columns:
            rows = connection.execute("SELECT match_type, pattern, category FROM rules ORDER BY pattern").fetchall()

            return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]

        rows = connection.execute("SELECT description, category FROM rules ORDER BY description").fetchall()

        return [("exact", str(row[0]), str(row[1])) for row in rows]
    finally:
        connection.close()


def restore_rules(connection: sqlite3.Connection, rows: Sequence[tuple[str, str, str]]) -> int:
    """Re-insert preserved fixture rules after the migrations have rebuilt the tables."""
    if not rows:
        return 0

    declared = {row["name"] for row in connection.execute("SELECT name FROM categories")}
    restored = 0
    restored_at = now_iso()

    with connection:
        for match_type, pattern, category in rows:
            # A category removed by a later migration drops its rules rather than resurrecting them.
            if category not in declared:
                continue

            cursor = connection.execute(
                "INSERT INTO rules (match_type, pattern, category, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (match_type, pattern, category, restored_at, restored_at),
            )
            restored += cursor.rowcount

    return restored
