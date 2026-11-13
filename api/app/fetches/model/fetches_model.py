"""The typed shapes of a fetch: the window requested, the row recorded, and what came back."""

import sqlite3
from dataclasses import dataclass
from datetime import date

from app.common.dates import day_start_epoch


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
    """One stored `data_fetches` row: when it ran, whether its data is usable, and why not."""

    fetched_at: str
    status: str
    error_code: str | None

    @staticmethod
    def from_row(row: sqlite3.Row) -> "FetchRecord":
        return FetchRecord(
            fetched_at=str(row["fetched_at"]),
            status=str(row["status"]),
            error_code=None if row["error_code"] is None else str(row["error_code"]),
        )


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
