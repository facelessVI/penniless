"""The account errors: a key that names no stored account, an update that cannot be applied, a
label name the vocabulary refuses, and a change only a cash account allows."""


class UnknownAccountError(Exception):
    """An account key that matches no stored row."""


class AccountUpdateError(Exception):
    """An update that carries no fields at all."""


class AccountDescriptionError(Exception):
    """A description past the length a note may have."""


class AccountNameError(Exception):
    """A cash account created without a name. No fetch will ever name it later, so it has to have one."""


class ManualAccountError(Exception):
    """The account came from a fetch, so its balance arrives with it and its row is not the user's to delete."""


class LabelNameError(ValueError):
    """A label name is blank, too long, carries a slash, or appears twice in one set."""
