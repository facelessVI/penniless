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

from app import categorize, errors, ledger

# Every domain error the API translates, with the status it answers with. A 400 is a
# request the caller can fix; a 404 is a key that names nothing stored.
DOMAIN_ERROR_STATUSES: dict[type[Exception], int] = {
    ledger.InvalidDateRangeError: 400,
    categorize.CategoryRulesError: 400,
    categorize.CategoryNameError: 400,
    categorize.ProtectedCategoryError: 400,
    categorize.RulePatternError: 400,
    categorize.UnknownRuleError: 400,
    categorize.UnknownCategoryError: 404,
    categorize.UnknownTransactionError: 404,
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


def register_exception_handlers(app: FastAPI) -> None:
    for error_class, status_code in DOMAIN_ERROR_STATUSES.items():
        app.add_exception_handler(error_class, status_handler(status_code))

    app.add_exception_handler(errors.SimpleFinError, simplefin_handler)
