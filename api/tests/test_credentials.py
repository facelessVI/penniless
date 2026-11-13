"""The SimpleFIN access URL is a bearer credential: one file per source, never one shared file.

No network and no database. The only thing under test is which file a read or a write lands in, so
every case runs against pytest's temporary directory with the source swapped on the module.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from app.common import credentials
from app.common.config import Settings, Source
from app.common.config import settings as current_settings

LIVE_ACCESS_URL = "https://demo:secret@bridge.simplefin.org/simplefin/accounts"
FIXTURE_ACCESS_URL = "https://fixture.invalid/accounts"


def settings_for(source: Source, data_dir: Path) -> Settings:
    """The same machine, the same data directory, a different mode."""
    return replace(current_settings, source=source, data_dir=data_dir)


def test_fixture_claim_cannot_be_read_by_live_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fixture connect writes a placeholder that can never resolve; live mode must not see it."""
    monkeypatch.setattr(credentials, "settings", settings_for("fixture", tmp_path))

    written = credentials.write_credentials(FIXTURE_ACCESS_URL)

    assert written.access_url == FIXTURE_ACCESS_URL

    live_path = tmp_path / "credentials-live.json"
    fixture_path = tmp_path / "credentials-fixture.json"

    assert fixture_path.is_file()
    assert not live_path.exists()
    assert (fixture_path.stat().st_mode & 0o777) == 0o600

    monkeypatch.setattr(credentials, "settings", settings_for("live", tmp_path))

    assert credentials.read_credentials() is None


def test_live_claim_survives_a_later_fixture_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The reverse direction: demoing fixture data must not cost a working live credential."""
    monkeypatch.setattr(credentials, "settings", settings_for("live", tmp_path))
    credentials.write_credentials(LIVE_ACCESS_URL)

    monkeypatch.setattr(credentials, "settings", settings_for("fixture", tmp_path))
    credentials.write_credentials(FIXTURE_ACCESS_URL)

    monkeypatch.setattr(credentials, "settings", settings_for("live", tmp_path))
    stored = credentials.read_credentials()

    assert stored is not None
    assert stored.access_url == LIVE_ACCESS_URL
    assert credentials.credentials_path() == tmp_path / "credentials-live.json"
    assert credentials.credentials_path() != tmp_path / "credentials-fixture.json"
