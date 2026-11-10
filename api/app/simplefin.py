"""SimpleFIN transport: claim a setup token, fetch a window, or replay the committed fixtures.

Both implementations sit behind `AccountSource`, so ingest never knows which one it has.
"""

import base64
import binascii
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from app.config import settings
from app.errors import (
    INVALID_BASE64_MESSAGE,
    INVALID_CLAIM_URL_MESSAGE,
    SimpleFinError,
    access_rejected_error,
    claim_rejected_error,
    invalid_setup_token_error,
    payment_required_error,
    upstream_error,
)
from app.schemas import SimpleFinAccount, SimpleFinAccountSet, SimpleFinConnection, SimpleFinTransaction

REQUEST_TIMEOUT_SECONDS = 30.0
FIXTURE_ACCESS_URL = "https://fixture.invalid/accounts"
FIXTURE_REJECTED_CLAIM_SUFFIX = "/claim/used"


class AccountSource(Protocol):
    def claim(self, setup_token: str) -> str: ...

    def fetch(self, access_url: str, start_epoch: int, end_epoch: int) -> SimpleFinAccountSet: ...


def decode_setup_token(setup_token: str) -> str:
    """A setup token is base64 of an https claim URL. Reject anything else before touching a socket."""
    try:
        decoded = base64.b64decode(setup_token.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError) as error:
        raise invalid_setup_token_error(INVALID_BASE64_MESSAGE) from error

    claim_url = decoded.strip()

    if not claim_url.startswith("https://"):
        raise invalid_setup_token_error(INVALID_CLAIM_URL_MESSAGE)

    return claim_url


def split_access_url(access_url: str) -> tuple[str, tuple[str, str] | None]:
    """Strip the Basic Auth userinfo out of the access URL, returning it separately."""
    parsed = urlsplit(access_url)

    if parsed.scheme != "https":
        raise SimpleFinError("The stored access URL is not https. Refusing to send the credential over plain HTTP.")

    host = parsed.hostname or ""
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    base_url = urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))
    auth = None

    if parsed.username is not None:
        auth = (unquote(parsed.username), unquote(parsed.password or ""))

    return base_url, auth


def error_code_from_body(body: str) -> str | None:
    try:
        account_set = SimpleFinAccountSet.model_validate_json(body)
    except ValidationError:
        return None

    return account_set.errlist[0].code if account_set.errlist else None


class LiveSimpleFin:
    def claim(self, setup_token: str) -> str:
        claim_url = decode_setup_token(setup_token)

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
                response = client.post(claim_url)
        except httpx.HTTPError as error:
            raise SimpleFinError(f"Could not reach the SimpleFIN claim URL ({error.__class__.__name__}).") from error

        if response.status_code == 403:
            raise claim_rejected_error()

        if response.status_code != 200:
            raise upstream_error(response.status_code, response.text)

        access_url = response.text.strip()

        if not access_url.startswith("https://"):
            raise SimpleFinError("SimpleFIN returned a claim result that is not an https access URL.")

        return access_url

    def fetch(self, access_url: str, start_epoch: int, end_epoch: int) -> SimpleFinAccountSet:
        base_url, auth = split_access_url(access_url)
        params = {"version": "2", "start-date": str(start_epoch), "end-date": str(end_epoch)}

        # `pending` is deliberately never sent: a pending row reappears later with a new id.
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, auth=auth) as client:
                response = client.get(f"{base_url}/accounts", params=params)
        except httpx.HTTPError as error:
            raise SimpleFinError(f"Could not reach SimpleFIN ({error.__class__.__name__}).") from error

        if response.status_code == 402:
            raise payment_required_error(error_code_from_body(response.text))

        if response.status_code == 403:
            raise access_rejected_error(error_code_from_body(response.text))

        if response.status_code != 200:
            raise upstream_error(response.status_code, response.text)

        try:
            return SimpleFinAccountSet.model_validate_json(response.text)
        except ValidationError as error:
            raise SimpleFinError(
                f"SimpleFIN returned a payload this app cannot read ({error.error_count()} problem(s))."
            ) from error


class FixtureSimpleFin:
    """Replays the committed fixture files. Never opens a socket."""

    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = fixture_dir

    def claim(self, setup_token: str) -> str:
        claim_url = decode_setup_token(setup_token)

        if claim_url.rstrip("/").endswith(FIXTURE_REJECTED_CLAIM_SUFFIX):
            raise claim_rejected_error()

        return FIXTURE_ACCESS_URL

    def fetch(self, access_url: str, start_epoch: int, end_epoch: int) -> SimpleFinAccountSet:
        account_set = load_fixture_account_set(self.fixture_dir)

        return filter_account_set(account_set, start_epoch, end_epoch)


def load_fixture_account_set(fixture_dir: Path) -> SimpleFinAccountSet:
    """Merge every fixture file: newest balance wins, transactions are deduplicated."""
    paths = sorted(fixture_dir.glob("accounts-*.json"))

    if not paths:
        raise SimpleFinError(f"No SimpleFIN fixtures found in {fixture_dir}.")

    connections: dict[str, SimpleFinConnection] = {}
    accounts: dict[tuple[str, str], SimpleFinAccount] = {}
    transactions: dict[tuple[str, str], dict[str, SimpleFinTransaction]] = {}

    for path in paths:
        account_set = SimpleFinAccountSet.model_validate_json(path.read_text(encoding="utf-8"))

        for connection in account_set.connections:
            connections[connection.conn_id] = connection

        for account in account_set.accounts:
            key = (account.conn_id or "", account.id)
            accounts[key] = account.model_copy(update={"transactions": []})
            bucket = transactions.setdefault(key, {})

            for transaction in account.transactions:
                bucket[transaction.id] = transaction

    merged_accounts = [
        account.model_copy(update={"transactions": list(transactions[key].values())})
        for key, account in accounts.items()
    ]

    return SimpleFinAccountSet(
        errlist=[],
        connections=list(connections.values()),
        accounts=merged_accounts,
    )


def filter_account_set(account_set: SimpleFinAccountSet, start_epoch: int, end_epoch: int) -> SimpleFinAccountSet:
    """Behave like a server: balances always come back, transactions only inside the window."""
    accounts = [
        account.model_copy(
            update={
                "transactions": [
                    transaction
                    for transaction in account.transactions
                    if transaction.posted is not None and start_epoch <= transaction.posted < end_epoch
                ]
            }
        )
        for account in account_set.accounts
    ]

    return account_set.model_copy(update={"accounts": accounts})


def get_account_source() -> AccountSource:
    if settings.source == "fixture":
        return FixtureSimpleFin(settings.fixture_dir)

    return LiveSimpleFin()
