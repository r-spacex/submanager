"""Common Pydantic parsing and validation types used by models."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import re
from typing import (
    TYPE_CHECKING,
    Pattern,
)

# Third party imports
import pydantic

# Hack so that mypy interprets the Pydantic validation types correctly

if TYPE_CHECKING:
    StrPattern = Pattern[str]
    NonEmptyStr = str
    StripStr = str
    ItemIDStr = str
    ThreadIDStr = str
else:
    StrPattern = Pattern

    class NonEmptyStr(pydantic.ConstrainedStr):
        """A non-emptry string type."""

        min_length = 1
        strict = True

    class StripStr(NonEmptyStr):
        """A string with whitespace stripped."""

        strip_whitespace = True

    class ItemIDStr(NonEmptyStr):
        """String reprisenting an item ID in the config dict."""

        regex = re.compile(r"[a-zA-Z0-9_\.]+")

    class ThreadIDStr(StripStr):
        """Pydantic type class for a thread ID of exactly 6 characters."""

        max_length = 6
        min_length = 6
        regex = re.compile("[a-z0-9]+")
        to_lower = True
