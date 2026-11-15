"""The account errors: a key that names no stored account, and an update that cannot be applied."""


class UnknownAccountError(Exception):
    """An account key that matches no stored row."""


class AccountUpdateError(Exception):
    """An update that carries no fields at all."""


class AccountDescriptionError(Exception):
    """A description past the length a note may have."""
