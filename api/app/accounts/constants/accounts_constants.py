"""Account types that do not count as cash.

The Bridge sends no account type for most institutions. When it does supply `extra.type`, only
these are demoted out of the cash total; anything unknown or missing stays in, which keeps the
total conservative until it is corrected with the UI toggle.
"""

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
