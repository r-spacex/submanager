"""Miscellaneous utility functions and classes."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import time

# Third party imports
from typing_extensions import (
    Final,
)

SLEEP_TICK_DEFAULT: Final[float] = 0.1


def sleep_for_interval(
    sleep_interval: float,
    sleep_tick: float = SLEEP_TICK_DEFAULT,
) -> None:
    """Sleep for the designated interval in small increments."""
    time_left_s = sleep_interval
    while True:
        time_to_sleep_s = min((time_left_s, sleep_tick))
        time.sleep(time_to_sleep_s)
        time_left_s -= sleep_tick
        if time_left_s <= 0:
            return
