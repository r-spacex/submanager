#!/usr/bin/env python3
"""Check if an appropriate Python environment is activated."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import sys
from pathlib import (
    Path,
)

# Third party imports
import praw

EXIT_BADFILE = 3
PY_TYPED_FILENAME = "py.typed"


def ensure_py_typed_exists() -> bool:
    """Ensure the py.typed file exists for praw, creating it if necessary."""
    py_typed_path = Path(praw.__file__).parent / PY_TYPED_FILENAME
    if py_typed_path.exists():
        return True

    print(f"Creating PRAW py.typed at {py_typed_path.as_posix()!r}")
    py_typed_path.touch()
    return False


def main() -> None:
    """Ensure the py.typed file exists for PRAW and handle any errors."""
    try:
        ensure_py_typed_exists()
    except Exception as error:
        error_message = f"{type(error).__name__}: {error}"
        messages = [
            "",
            "*" * 70,
            "ERROR: praw/py.typed does not exist and could not create it",
            "It may be installed as a ZIP, using system Python or with root",
            "This means the MyPy typechecker will not pick up PRAW's types",
            "Install/activate a venv, or create it manually (see PEP 561)",
            "",
            error_message,
            "*" * 70,
            "",
        ]
        print("\n".join(messages), file=sys.stderr)
        sys.exit(EXIT_BADFILE)


if __name__ == "__main__":
    main()
