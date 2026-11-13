"""Local calendar dates, which is how SimpleFIN windows, posting dates and balances are read here."""

from datetime import date, datetime, time


def day_start_epoch(day: date) -> int:
    """Midnight local time for a calendar date, which is how SimpleFIN windows are read here."""
    return int(datetime.combine(day, time.min).timestamp())


def local_date(epoch_seconds: int) -> date:
    return datetime.fromtimestamp(epoch_seconds).date()
