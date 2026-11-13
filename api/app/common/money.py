"""Money on the wire is integer cents. SimpleFIN sends numeric strings, so parse without float."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTS_PER_UNIT = Decimal(100)


def parse_cents(value: str | int | float | Decimal | None) -> int | None:
    """Convert a SimpleFIN numeric string such as "-20.00" to whole cents, without float drift."""
    if value is None:
        return None

    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"not a monetary amount: {value!r}") from error

    if not amount.is_finite():
        raise ValueError(f"not a finite monetary amount: {value!r}")

    return int((amount * CENTS_PER_UNIT).to_integral_value(rounding=ROUND_HALF_UP))
