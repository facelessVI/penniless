"""Domain exceptions to HTTP responses: the one place a status code is chosen.

Routers raise domain exceptions and never translate them, so the statuses the API can
answer with are declared here rather than repeated in every handler. FastAPI matches a
handler by walking the exception's class hierarchy, so a subclass of a registered error
is answered by the same handler.
"""

from collections.abc import Callable
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.accounts.errors.accounts_errors import UnknownAccountError
from app.categories.errors.categories_errors import (
    CategoryNameError,
    CategoryOrderError,
    CategoryRulesError,
    ProtectedCategoryError,
    RulePatternError,
    UnknownCategoryError,
    UnknownRuleError,
    UnknownTransactionError,
)
from app.common import errors
from app.setup.errors.setup_errors import (
    AlreadyConnectedError,
    NotConnectedError,
    RefreshNotAllowedError,
)
from app.transactions.errors.transactions_errors import InvalidDateRangeError

# Every domain error the API translates, with the status it answers with. A 400 is a
# request the caller can fix; a 404 is a key that names nothing stored.
DOMAIN_ERROR_STATUSES: dict[type[Exception], int] = {
    InvalidDateRangeError: 400,
    CategoryRulesError: 400,
    CategoryNameError: 400,
    CategoryOrderError: 400,
    ProtectedCategoryError: 400,
    RulePatternError: 400,
    UnknownRuleError: 400,
    UnknownAccountError: 404,
    UnknownCategoryError: 404,
    UnknownTransactionError: 404,
    AlreadyConnectedError: 409,
    NotConnectedError: 409,
}


def status_handler(status_code: int) -> Callable[[Request, Exception], JSONResponse]:
    """A handler that answers with FastAPI's own `{"detail": ...}` shape and a fixed status."""

    def handler(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handler


def simplefin_handler(_: Request, error: Exception) -> JSONResponse:
    """A SimpleFIN failure decides its own status and has already sanitized its message."""
    failure = cast(errors.SimpleFinError, error)

    return JSONResponse(status_code=failure.status_code, content={"detail": failure.message})


def refresh_not_allowed_handler(_: Request, error: Exception) -> JSONResponse:
    """The one body that carries more than a detail: the guard tells the UI when to try again."""
    failure = cast(RefreshNotAllowedError, error)

    # A hand-built body is not aliased by ApiModel, so it spells the camelCase keys itself.
    return JSONResponse(
        status_code=429,
        content={
            "detail": str(failure),
            "refreshAllowed": False,
            "nextRefreshAllowedAt": failure.next_allowed_at,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    for error_class, status_code in DOMAIN_ERROR_STATUSES.items():
        app.add_exception_handler(error_class, status_handler(status_code))

    app.add_exception_handler(errors.SimpleFinError, simplefin_handler)
    app.add_exception_handler(RefreshNotAllowedError, refresh_not_allowed_handler)
