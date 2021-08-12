"""Tools for parsing, conversion and utilities on Pydantic models."""

# Future imports
from __future__ import (
    annotations,
)


class MissingAccount:
    """Reprisent missing account keys."""

    def __init__(self, key: str) -> None:
        self.key = key

    def __str__(self) -> str:
        """Convert the class to a string."""
        return str(self.key)


def process_raw_interval(raw_interval: str) -> tuple[str, int | None]:
    """Convert a time interval expressed as a string into a standard form."""
    interval_split = raw_interval.strip().split()

    # Extract the number of time units
    if len(interval_split) == 1:
        interval_n = None
    else:
        interval_n = int(interval_split[0])

    # Extract the time unit
    interval_unit = interval_split[-1]
    interval_unit = interval_unit.rstrip("s")
    if interval_unit[-2:] == "ly":
        interval_unit = interval_unit[:-2]
    if interval_unit == "week" and not interval_n:
        interval_n = 1

    return interval_unit, interval_n
