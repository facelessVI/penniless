"""Turning SimpleFIN failures into HTTP responses, and keeping anything sensitive out of them."""

import re

from fastapi import HTTPException

MAX_MESSAGE_LENGTH = 300
USERINFO_PATTERN = re.compile(r"//[^/@\s]+@")

CLAIM_REJECTED_MESSAGE = (
    "That setup token has already been used, or it is compromised. Create a fresh token at the "
    "SimpleFIN Bridge and try again."
)
ACCESS_REJECTED_MESSAGE = (
    "SimpleFIN rejected the stored access URL. Access may have been revoked; connect again with a fresh setup token."
)
PAYMENT_REQUIRED_MESSAGE = "SimpleFIN reports that the Bridge subscription needs payment."
NOT_CONNECTED_MESSAGE = "No access URL is stored yet. Connect with a setup token first."
ALREADY_CONNECTED_MESSAGE = "Already connected. Send replace=true to claim a new access URL."
INVALID_BASE64_MESSAGE = "setup token is not valid base64"
INVALID_CLAIM_URL_MESSAGE = "setup token does not decode to an https claim URL"


def sanitize_message(message: str) -> str:
    """Make a server-supplied message safe to show and log: no control characters, no credentials."""
    without_credentials = USERINFO_PATTERN.sub("//<redacted>@", message or "")
    printable_only = "".join(character for character in without_credentials if character.isprintable())
    collapsed = " ".join(printable_only.split())

    if len(collapsed) > MAX_MESSAGE_LENGTH:
        return collapsed[: MAX_MESSAGE_LENGTH - 3] + "..."

    return collapsed


class SimpleFinError(Exception):
    """A SimpleFIN failure with the HTTP status and protocol code the caller should record."""

    def __init__(self, message: str, status_code: int = 502, error_code: str | None = None) -> None:
        self.message = sanitize_message(message)
        self.status_code = status_code
        self.error_code = error_code

        super().__init__(self.message)


def invalid_setup_token_error(message: str) -> SimpleFinError:
    return SimpleFinError(message=message, status_code=400)


def claim_rejected_error() -> SimpleFinError:
    return SimpleFinError(message=CLAIM_REJECTED_MESSAGE, status_code=403)


def access_rejected_error(error_code: str | None = None) -> SimpleFinError:
    return SimpleFinError(message=ACCESS_REJECTED_MESSAGE, status_code=403, error_code=error_code)


def payment_required_error(error_code: str | None = None) -> SimpleFinError:
    return SimpleFinError(message=PAYMENT_REQUIRED_MESSAGE, status_code=402, error_code=error_code)


def upstream_error(status_code: int, body: str = "", error_code: str | None = None) -> SimpleFinError:
    detail = sanitize_message(body)
    message = f"SimpleFIN returned HTTP {status_code}."

    if detail:
        message = f"SimpleFIN returned HTTP {status_code}: {detail}"

    return SimpleFinError(message=message, status_code=502, error_code=error_code)


def not_connected_error() -> HTTPException:
    return HTTPException(status_code=409, detail=NOT_CONNECTED_MESSAGE)
