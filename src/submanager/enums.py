"""Common enums and enum types used throughout the package."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import enum

# ---- Enum subclasses ----


# Replace with StrEnum in Python 3.10 (?)
class StrValueEnum(enum.Enum):
    """Normalizes input and outputs just value as repr for serialization."""

    value: str  # pylint: disable = invalid-name

    def __repr__(self) -> str:
        """Convert enum value to repr."""
        return str(self.value)

    def __str__(self) -> str:
        """Convert enum value to string."""
        return str(self.value)

    @classmethod  # noqa: WPS120
    def _missing_(cls, value: object) -> StrValueEnum | None:  # noqa: WPS120
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

    value: int  # pylint: disable = invalid-name

    SUCCESS = 0
    ERROR_UNHANDLED = 1
    ERROR_PARAMETERS = 2
    ERROR_USER = 3


@enum.unique
class EndpointType(StrValueEnum):
    """Reprisent the type of sync endpoint on Reddit."""

    MENU = "menu"
    THREAD = "thread"
    WIDGET = "widget"
    WIKI_PAGE = "wiki_page"


@enum.unique
class PinMode(StrValueEnum):
    """Reprisent the type of thread pinning behavior on Reddit."""

    NONE = "none"
    AUTO = "auto"
    BOTTOM = "bottom"
    TOP = "top"
