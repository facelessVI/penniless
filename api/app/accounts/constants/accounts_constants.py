"""Account values that are not SQL: where an account came from, the account types that do not
count as cash, the note's cap, and the name rule the label vocabulary follows.

The Bridge sends no account type for most institutions. When it does supply `extra.type`, only
these are demoted out of the cash total; anything unknown or missing stays in, which keeps the
total conservative until it is corrected with the UI toggle.
"""

from app.accounts.errors.accounts_errors import LabelNameError
from app.common.names import NameRule

SIMPLEFIN_SOURCE = 1
"""The account arrives with a fetch, and every fetch rewrites its balance."""

MANUAL_SOURCE = 2
"""The user created the account by hand, so its balance is theirs to set and its key is theirs to delete."""

MANUAL_CONNECTION_ID = "manual"
"""A cash account belongs to no connection, but the accounts key is composite, so it still needs one."""

MANUAL_CONNECTION_NAME = "Manual"
MANUAL_CURRENCY = "USD"

NON_CASH_ACCOUNT_TYPES = {
    "credit",
    "credit card",
    "loan",
    "mortgage",
    "student loan",
    "auto loan",
    "investment",
    "brokerage",
    "retirement",
}

DESCRIPTION_MAXIMUM_LENGTH = 500

LABEL_NAME_RULE = NameRule(noun="label", error=LabelNameError)
