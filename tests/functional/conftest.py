"""Common functional test fixtures."""

# Future imports
from __future__ import annotations

# Standard library imports
import subprocess
import sys
from typing import (
    Callable  # Import from collections.abc in Python 3.9
    )

# Third party imports
import pytest
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )


# ---- Constants ----

InvokeCommand = Callable[[str], subprocess.CompletedProcess[str]]

PACKAGE_NAME: Final[str] = "submanager"
ENTRYPOINT_NAME: Final[str] = PACKAGE_NAME

INVOCATION_RUNPY: Final[list[str]] = [
    sys.executable, "-b", "-X", "dev", "-m", PACKAGE_NAME]
INVOCATION_IDS: Final[list[str]] = [
    "entrypoint",
    "runpy",
    ]
INVOCATION_METHODS: Final[list[list[str]]] = [
    [ENTRYPOINT_NAME],
    INVOCATION_RUNPY,
    ]


# ---- Fixtures ----

@pytest.fixture(params=INVOCATION_METHODS, ids=INVOCATION_IDS)
def invoke_command(
        request: pytest.FixtureRequest,
        ) -> InvokeCommand:
    """Invoke the passed command with a given invocation."""
    def _invoke_command(command: str) -> subprocess.CompletedProcess[str]:
        invocation: list[str] = request.param  # type: ignore[attr-defined]
        process_result = subprocess.run(
            invocation + [command],
            capture_output=True,
            check=False,
            encoding="utf-8",
            text=True,
            )
        return process_result
    return _invoke_command
