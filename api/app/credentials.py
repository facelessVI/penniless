"""The SimpleFIN access URL is a bearer credential. It lives in one 0600 file per mode, never leaves it."""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import CREDENTIALS_FILENAMES, settings

CREDENTIALS_MODE = 0o600


@dataclass(frozen=True)
class Credentials:
    access_url: str
    claimed_at: str

    def __repr__(self) -> str:
        return f"Credentials(access_url=<redacted>, claimed_at={self.claimed_at!r})"

    __str__ = __repr__


def credentials_path() -> Path:
    """The file for the mode this process runs in, so a fixture claim cannot displace a live one."""
    return settings.data_dir / CREDENTIALS_FILENAMES[settings.source]


def read_credentials() -> Credentials | None:
    path = credentials_path()

    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))

    return Credentials(access_url=payload["access_url"], claimed_at=payload["claimed_at"])


def write_credentials(access_url: str, claimed_at: datetime | None = None) -> Credentials:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    claimed_at_iso = (claimed_at or datetime.now(UTC)).isoformat(timespec="seconds")
    payload = json.dumps({"access_url": access_url, "claimed_at": claimed_at_iso}, indent=2) + "\n"

    # os.open with an explicit mode creates the file already at 0600, leaving no window in which
    # the credential exists with wider permissions.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, CREDENTIALS_MODE)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
    finally:
        os.chmod(path, CREDENTIALS_MODE)

    return Credentials(access_url=access_url, claimed_at=claimed_at_iso)
