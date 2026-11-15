"""The account errors: a key that names no stored account, an update that cannot be applied, and a
label name the vocabulary refuses."""


class UnknownAccountError(Exception):
    """An account key that matches no stored row."""


class AccountUpdateError(Exception):
    """An update that carries no fields at all."""


class AccountDescriptionError(Exception):
    """A description past the length a note may have."""


class LabelNameError(ValueError):
    """A label name is blank, too long, carries a slash, or appears twice in one set."""
