"""Applying `migrations/*.sql` exactly once, in filename order.

Each file and its `schema_migrations` row travel in one transaction, so a migration that
fails part way leaves neither the schema change nor the bookkeeping behind.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.common.config import MIGRATIONS_DIR

MIGRATIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
)
"""


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


def reset_database(database_path: Path) -> None:
    """Delete the database file and its WAL sidecars, for the fixture-mode rebuild on startup."""
    for suffix in ("", "-wal", "-shm"):
        Path(f"{database_path}{suffix}").unlink(missing_ok=True)
