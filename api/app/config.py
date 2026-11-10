"""Environment-driven settings. Every path and mode the API reads comes from here."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

API_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = API_DIR / "migrations"
CATEGORIES_PATH = API_DIR / "categories.yaml"

Source = Literal["live", "fixture"]

# One database per mode, so fixture data and real money never share a file.
DATABASE_FILENAMES: dict[Source, str] = {
    "live": "penniless.sqlite",
    "fixture": "penniless-dev.sqlite",
}

DEFAULT_REFRESH_MIN_INTERVAL_HOURS = 6.0


def _path_from_env(variable: str, default: Path) -> Path:
    value = os.environ.get(variable)

    if value:
        return Path(value).expanduser().resolve()

    return default


def _parse_source(value: str) -> Source:
    if value not in DATABASE_FILENAMES:
        raise ValueError(f"PENNILESS_SOURCE must be 'live' or 'fixture', got {value!r}")

    return cast(Source, value)


def _parse_hours(variable: str, default: float) -> float:
    value = os.environ.get(variable)

    if not value:
        return default

    return float(value)


@dataclass(frozen=True)
class Settings:
    source: Source
    data_dir: Path
    database_path: Path
    fixture_dir: Path
    categories_path: Path
    refresh_min_interval_hours: float

    @staticmethod
    def from_environment() -> "Settings":
        source = _parse_source(os.environ.get("PENNILESS_SOURCE", "live"))
        data_dir = _path_from_env("PENNILESS_DATA_DIR", API_DIR / ".data")

        return Settings(
            source=source,
            data_dir=data_dir,
            database_path=_path_from_env("PENNILESS_DB_PATH", data_dir / DATABASE_FILENAMES[source]),
            fixture_dir=_path_from_env("PENNILESS_FIXTURE_DIR", API_DIR / "fixtures"),
            categories_path=_path_from_env("PENNILESS_CATEGORIES_PATH", CATEGORIES_PATH),
            refresh_min_interval_hours=_parse_hours(
                "PENNILESS_REFRESH_MIN_INTERVAL_HOURS", DEFAULT_REFRESH_MIN_INTERVAL_HOURS
            ),
        )


settings = Settings.from_environment()
