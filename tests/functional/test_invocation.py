"""Basic tests of invoking the main entrypoint."""

# Future imports
from __future__ import annotations

# Standard library imports
import subprocess
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

PARAMS_GOOD: Final[list[str]] = [
    "--help",
    "--version",
    ]
PARAMS_BAD: Final[list[str]] = [
    "--non-existant-flag",
    ]
PARAMS_BAD_EXIT_CODE = 2


# ---- Tests ----

@pytest.mark.parametrize("command", PARAMS_GOOD)
def test_invocation_good(
        invoke_command: InvokeCommand,
        command: str,
        ) -> None:
    """Test that the program is successfully invoked by different means."""
    process_result = invoke_command(command)
    assert process_result.returncode == 0
    assert process_result.stdout.strip()
    assert not process_result.stderr.strip()


@pytest.mark.parametrize("command", PARAMS_BAD)
def test_invocation_bad(
        invoke_command: InvokeCommand,
        command: str,
        ) -> None:
    """Test that the program fails when invoked with bad flags/args."""
    process_result = invoke_command(command)
    assert process_result.returncode == PARAMS_BAD_EXIT_CODE
    assert process_result.stderr.strip()
    assert not process_result.stdout.strip()
