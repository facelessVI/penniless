"""How a pattern decides a description, and the keywords one description could be taught by.

Pure functions and no data classes: precedence lives with the rule model, and nothing here
touches a connection, so the interesting cases are testable without one.
"""

import string
from collections.abc import Sequence

from app.categories.constants.categories_constants import (
    KEYWORD_NOISE_TOKENS,
    MATCH_TYPE_EXACT,
    MINIMUM_KEYWORD_TOKEN_LENGTH,
)


def matches(match_type: str, pattern: str, description: str) -> bool:
    """`exact` is the whole description and stays case-sensitive; `contains` is a substring."""
    if match_type == MATCH_TYPE_EXACT:
        return pattern == description

    return pattern.casefold() in description.casefold()


def count_matches(descriptions: Sequence[str], match_type: str, pattern: str) -> int:
    """How many stored rows a candidate rule would match, through the same helper classify uses."""
    return sum(1 for description in descriptions if matches(match_type, pattern, description))


def keyword_token(word: str) -> str | None:
    """One word as a keyword, or `None` when it says nothing about the merchant."""
    token = word.strip(string.punctuation)

    if len(token) < MINIMUM_KEYWORD_TOKEN_LENGTH:
        return None

    if any(character.isdigit() for character in token):
        return None

    if not any(character.isalpha() for character in token):
        return None

    if token.casefold() in KEYWORD_NOISE_TOKENS:
        return None

    return token


def keyword_tokens(description: str) -> list[str]:
    """The description's words a keyword could plausibly be: no digits, no short words, no noise."""
    return [token for word in description.split() if (token := keyword_token(word)) is not None]


def keyword_phrases(description: str) -> list[str]:
    """Two neighbouring words, so a merchant whose useful part spans a boundary is still offered.

    Adjacency is read from the description, not from the filtered word list, and the phrase is only
    kept when it occurs in the description as written. Sorting the words first would offer pairs the
    user never saw and that match nothing.
    """
    words = description.split()
    qualifiers = [keyword_token(word) for word in words]
    phrases: list[str] = []

    for index in range(len(words) - 1):
        first = qualifiers[index]
        second = qualifiers[index + 1]

        if first is None or second is None:
            continue

        phrase = f"{first} {second}"

        if phrase.casefold() not in description.casefold():
            continue

        phrases.append(phrase)

    return phrases
