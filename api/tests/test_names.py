"""The one name rule every named vocabulary shares: trim, non-blank, capped, slash-free, unique.

No database and no network. Each package answers "which spelling does this name already have" from
its own table and hands that spelling in, so the rule decides uniqueness without knowing the table.
The error class is the caller's, so each package keeps its own 400 and its own wording.
"""

import pytest

from app.common import names


class WidgetNameError(ValueError):
    """A stand-in for a package's own error class: the rule must raise the class it was given."""


RULE = names.NameRule(noun="widget", error=WidgetNameError)


def test_normalize_trims_the_ends_and_keeps_the_spacing_inside() -> None:
    assert RULE.normalize("  Home  Lab  ") == "Home  Lab"


@pytest.mark.parametrize("name", ["", "   "])
def test_normalize_rejects_a_blank_name(name: str) -> None:
    with pytest.raises(WidgetNameError, match="needs a name"):
        RULE.normalize(name)


def test_normalize_accepts_the_cap_and_rejects_one_character_more() -> None:
    assert RULE.normalize("x" * 40) == "x" * 40

    with pytest.raises(WidgetNameError, match="at most 40 characters"):
        RULE.normalize("x" * 41)


def test_normalize_rejects_a_slash() -> None:
    with pytest.raises(WidgetNameError, match="slash"):
        RULE.normalize("Home/Lab")


def test_ensure_is_free_allows_a_name_no_row_carries() -> None:
    RULE.ensure_is_free("Home Lab", None)


def test_ensure_is_free_rejects_a_taken_name_in_any_casing() -> None:
    with pytest.raises(WidgetNameError, match="already a widget"):
        RULE.ensure_is_free("home lab", "Home Lab")


def test_ensure_is_free_allows_a_rename_that_only_changes_the_casing_of_its_own_name() -> None:
    RULE.ensure_is_free("HOME LAB", "Home Lab", current_name="Home Lab")
