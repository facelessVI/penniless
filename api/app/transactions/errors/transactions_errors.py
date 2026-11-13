"""A request that asks for an impossible window.

Both dates are inclusive, so a start after the end matches nothing; the caller can fix it.
"""


class InvalidDateRangeError(ValueError):
    """`start` is after `end`, so the range names no days."""
