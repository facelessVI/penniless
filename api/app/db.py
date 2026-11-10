"""SQLite access: connections, the migration runner, fixture reset, and SimpleFIN money parsing."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from app.config import MIGRATIONS_DIR, settings

CENTS_PER_UNIT = Decimal(100)

MIGRATIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
)
"""


def connect(database_path: Path | None = None) -> sqlite3.Connection:
    path = database_path if database_path is not None else settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
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


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run_migrations(connection: sqlite3.Connection) -> list[str]:
    """Apply every migration file not yet recorded, in filename order. Returns the files applied."""
    connection.execute(MIGRATIONS_TABLE_DDL)
    connection.commit()

    applied_filenames = {row["filename"] for row in connection.execute("SELECT filename FROM schema_migrations")}
    newly_applied: list[str] = []

    for path in migration_files():
        if path.name in applied_filenames:
            continue

        apply_migration(connection, path)
        newly_applied.append(path.name)

    return newly_applied


def apply_migration(connection: sqlite3.Connection, path: Path) -> None:
    """Run one migration file and record it in the same SQLite transaction."""
    sql = path.read_text(encoding="utf-8")
    applied_at = datetime.now(UTC).isoformat(timespec="seconds")
    escaped_filename = path.name.replace("'", "''")

    # executescript has no parameter binding and commits any open transaction first, so the
    # migration and its bookkeeping row travel together in the script's own transaction. The
    # lone `;` terminates a file whose last statement lost its semicolon.
    script = (
        f"BEGIN;\n{sql}\n;\n"
        f"INSERT INTO schema_migrations (filename, applied_at) VALUES ('{escaped_filename}', '{applied_at}');\n"
        "COMMIT;\n"
    )

    try:
        connection.executescript(script)
    except sqlite3.Error:
        connection.rollback()
        raise


def now_iso() -> str:
    """Timestamps land in SQLite as UTC; only calendar dates are local."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def reset_database(database_path: Path | None = None) -> None:
    """Delete the database file and its WAL sidecars, for the fixture-mode rebuild on startup."""
    path = database_path if database_path is not None else settings.database_path

    for suffix in ("", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def parse_cents(value: str | int | float | Decimal | None) -> int | None:
    """Convert a SimpleFIN numeric string such as "-20.00" to whole cents, without float drift."""
    if value is None:
        return None

    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"not a monetary amount: {value!r}") from error

    if not amount.is_finite():
        raise ValueError(f"not a finite monetary amount: {value!r}")

    return int((amount * CENTS_PER_UNIT).to_integral_value(rounding=ROUND_HALF_UP))
