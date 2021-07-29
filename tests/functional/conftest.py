"""Common functional test fixtures."""

# Future imports
from __future__ import annotations

# Standard library imports
import subprocess
import sys
from typing import (
    Callable,  # Import from collections.abc in Python 3.9
    TypeVar,
    Tuple,  # Not needed in Python 3.9
    Optional,  # Not needed in Python 3.10
    )

# Third party imports
import pytest
from _pytest.capture import (
    CaptureResult,
    )
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )

# Local imports
import submanager.cli


# ---- Constants ----

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


# ---- Types ----

ArgType = TypeVar("ArgType")
RunCLIOutput = Tuple[CaptureResult[str], Optional[SystemExit]]


# ---- Fixtures ----

@pytest.fixture
def run_cli(
        capfd: pytest.CaptureFixture[str],
        ) -> Callable[[list[str]], RunCLIOutput]:
    """Run the package CLI with the passed argument(s)."""
    def _run_cli(
            cli_args: list[str]) -> RunCLIOutput:
        captured_error = None
        try:
            submanager.cli.main(cli_args)
        except SystemExit as error:
            captured_error = error
        captured_output = capfd.readouterr()
        return captured_output, captured_error
    return _run_cli


@pytest.fixture(params=INVOCATION_METHODS, ids=INVOCATION_IDS)
def invoke_command(
        request: pytest.FixtureRequest,
        ) -> Callable[[str], subprocess.CompletedProcess[str]]:
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
