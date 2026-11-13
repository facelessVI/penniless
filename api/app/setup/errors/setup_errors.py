"""What went wrong with the connection lifecycle. `handlers` maps each to a status."""


class AlreadyConnectedError(ValueError):
    """An access URL is already stored and the caller did not ask to replace it."""


class NotConnectedError(ValueError):
    """Nothing to refresh or backfill with: no access URL has been claimed yet."""


class RefreshNotAllowedError(ValueError):
    """The quota guard is active, so another fetch would spend an allowance it may not have."""

    def __init__(self, next_allowed_at: str | None) -> None:
        self.next_allowed_at = next_allowed_at

        super().__init__(f"Refresh is not allowed yet. Next refresh allowed at {next_allowed_at}.")
