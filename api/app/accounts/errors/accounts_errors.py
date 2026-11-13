"""The account errors: a key that names no stored account, and nothing else yet."""


class UnknownAccountError(Exception):
    """An account key that matches no stored row."""
