"""The fetch window shape and the quota rule that decides when another fetch may happen."""

BACKFILL_MONTHS = 12
DAYS_PER_MONTH = 30.44

# The Bridge counts a requested range inclusive of both of its dates and caps a request at 90
# days, so windows are requested one day short of that: 89 days here is 90 days inclusive, which
# leaves no headroom for the cap to trim an answer. Its 45-day figure is a recommendation, and
# overrunning it produces a `gen.api` advisory rather than a failure (see ADVISORY_ERROR_CODES).
WINDOW_LENGTH_DAYS = 89
WINDOW_OVERLAP_DAYS = 5

# `gen.api` is the protocol's developer-facing namespace: "Error in how the API is being used. This
# is meant for the developer and not for the user." Every other code (`con.*`, `act.*`, `gen.auth`)
# is a failure the user needs to see, because accounts or transactions may be missing.
ADVISORY_ERROR_CODES = frozenset({"gen.api"})
