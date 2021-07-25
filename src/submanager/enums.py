"""Common enums and enum types used throughout the package."""

# Future imports
from __future__ import annotations

# Standard library imports
import enum


# ---- Enum subclasses ----

# Replace with StrEnum in Python 3.10 (?)
class StrValueEnum(enum.Enum):
    """Normalizes input and outputs just value as repr for serialization."""

    def __repr__(self) -> str:
        """Convert enum value to repr."""
        return str(self.value)

    def __str__(self) -> str:
        """Convert enum value to string."""
        return str(self.value)

    @classmethod
    def _missing_(cls, value: object) -> "StrValueEnum" | None:
        """Handle case-insensitive lookup of enum values."""
        if not isinstance(value, str):
            return None
        value = value.strip().lower().replace(" ", "_").replace("-", "_")
        for member in cls:
            if member.value.lower() == value:
                return member
        return None


# ---- Enum constants -----

@enum.unique
class ExitCode(enum.Enum):
    """Exit code signalling the type of exit from the program."""

    SUCCESS = 0
    ERROR_UNHANDLED = 1
    ERROR_USER = 3


@enum.unique
class EndpointType(StrValueEnum):
    """Reprisent the type of sync endpoint on Reddit."""

    MENU = "menu"
    THREAD = "thread"
    WIDGET = "widget"
    WIKI_PAGE = "wiki_page"


@enum.unique
class PinType(StrValueEnum):
    """Reprisent the type of thread pinning behavior on Reddit."""

    NONE = "none"
    BOTTOM = "bottom"
    TOP = "top"