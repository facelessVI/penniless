"""Environment-driven settings. Every path and mode the API reads comes from here."""

import os
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent


def _path_from_env(variable: str, default: Path) -> Path:
    value = os.environ.get(variable)

    if value:
        return Path(value).expanduser().resolve()

    return default


SOURCE = os.environ.get("PENNILESS_SOURCE", "live")
DATA_DIR = _path_from_env("PENNILESS_DATA_DIR", API_DIR / ".data")
DATABASE_PATH = _path_from_env("PENNILESS_DB_PATH", DATA_DIR / "penniless.sqlite")
