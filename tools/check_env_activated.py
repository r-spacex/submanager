#!/usr/bin/env python3
"""Check if an appropriate Python environment is activated."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import sys
from typing import (
    NoReturn,
)

EXIT_BADENV = 3


def handle_error(error: BaseException, message: str = "") -> NoReturn:
    """Handle the import error produced by a block."""
    error_message = f"{type(error).__name__}: {error}"
    messages = [
        "",
        "*" * 70,
        "ERROR: Suitible Python environment not activated",
        message,
        "",
        error_message,
        "*" * 70,
        "",
    ]
    print("\n".join(messages), file=sys.stderr)
    sys.exit(EXIT_BADENV)


def main() -> None:
    """Try importing key deps and fail with a friendly error message."""
    # pylint: disable = import-outside-toplevel
    # pylint: disable = too-many-try-statements
    # pylint: disable = unused-import
    try:
        # Third party imports
        import praw  # noqa: F401
        import pydantic  # noqa: F401
    except ImportError as error:
        handle_error(error=error, message="Runtime dependencies not found")

    try:
        # Third party imports
        import mypy  # noqa: F401
        import pyanalyze  # type: ignore[import]  # noqa: F401
        import pylint  # type: ignore[import]  # noqa: F401
    except ImportError as error:
        handle_error(error=error, message="Linting dependencies not found")


if __name__ == "__main__":
    main()
