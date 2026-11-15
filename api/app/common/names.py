"""The name rule every named vocabulary follows: trimmed, non-blank, capped, slash-free, unique.

There is one rule, not one per package: a category name and a label name are the same kind of name,
so they look and behave the same. The rule speaks in the caller's error class, which is why a package
passes its own: the message a user reads stays that package's wording and status.

Uniqueness needs the package's table, so the package does the lookup and the rule decides what the
spelling it found means - a rename that only changes casing is free, any other spelling is taken.
"""

from dataclasses import dataclass

MAXIMUM_NAME_LENGTH = 40


@dataclass(frozen=True)
class NameRule:
    noun: str
    error: type[ValueError]

    def normalize(self, name: str) -> str:
        """Trim the ends only: the spacing inside a name is what the user typed."""
        normalized = name.strip()

        if not normalized:
            raise self.error(f"A {self.noun} needs a name.")

        if len(normalized) > MAXIMUM_NAME_LENGTH:
            raise self.error(f"A {self.noun} name can be at most {MAXIMUM_NAME_LENGTH} characters.")

        # The management endpoints address a name as a path segment, where a slash would split it and
        # turn a valid rename into a 404. Refusing it at the door is clearer than an unmatchable route.
        if "/" in normalized:
            raise self.error(f"A {self.noun} name cannot contain a slash.")

        return normalized

    def ensure_is_free(self, name: str, stored_name: str | None, current_name: str | None = None) -> None:
        """`stored_name` is the spelling the package's lookup found, or `None` when nothing holds it."""
        if stored_name is None:
            return

        if current_name is not None and stored_name.casefold() == current_name.casefold():
            return

        raise self.error(f"{name!r} is already a {self.noun}.")
