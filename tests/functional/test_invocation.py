"""Basic tests of invoking the main entrypoint."""

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
BAD_PARAMS_EXIT_CODE = 2

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

COMMANDS_GOOD: Final[list[str]] = [
    "--help",
    "--version",
    ]
COMMANDS_BAD: Final[list[str]] = [
    "--non-existant-flag",
    ]


# ---- Fixtures ----

@pytest.fixture(
    name="invoke_command", params=INVOCATION_METHODS, ids=INVOCATION_IDS)
def fixture_invoke_command(
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


# ---- Tests ----

@pytest.mark.parametrize("command", COMMANDS_GOOD)
def test_invocation_good(
        invoke_command: InvokeCommand,
        command: str,
        ) -> None:
    """Test that the program is successfully invoked by different means."""
    process_result = invoke_command(command)
    assert process_result.returncode == 0
    assert process_result.stdout.strip()
    assert not process_result.stderr.strip()


@pytest.mark.parametrize("command", COMMANDS_BAD)
def test_invocation_bad(
        invoke_command: InvokeCommand,
        command: str,
        ) -> None:
    """Test that the program fails when invoked with bad flags/args."""
    process_result = invoke_command(command)
    assert process_result.returncode == BAD_PARAMS_EXIT_CODE
    assert process_result.stderr.strip()
    assert not process_result.stdout.strip()
