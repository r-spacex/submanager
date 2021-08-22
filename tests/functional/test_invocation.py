"""Basic tests of invoking the main entrypoint."""

# Future imports
from __future__ import (
    annotations,
)

# Third party imports
import pytest
from typing_extensions import (
    Final,
)

# Local imports
import submanager.enums
from tests.functional.conftest import (
    InvokeCommandCallable,
)

# ---- Constants ----

PARAMS_GOOD: Final[list[str]] = [
    "--help",
    "--version",
]
PARAMS_BAD: Final[list[str]] = [
    "--non-existent-flag",
]


# ---- Tests ----


@pytest.mark.slow()
@pytest.mark.parametrize("command", PARAMS_GOOD)
def test_invocation_good(
    invoke_command: InvokeCommandCallable,
    command: str,
) -> None:
    """Test that the program is successfully invoked by different means."""
    process_result = invoke_command(command)

    assert not process_result.returncode
    assert process_result.returncode == submanager.enums.ExitCode.SUCCESS.value
    assert process_result.stdout.strip()
    assert not process_result.stderr.strip()


@pytest.mark.slow()
@pytest.mark.parametrize("command", PARAMS_BAD)
def test_invocation_bad(
    invoke_command: InvokeCommandCallable,
    command: str,
) -> None:
    """Test that the program fails when invoked with bad flags/args."""
    process_result = invoke_command(command)

    assert process_result.returncode
    assert (
        process_result.returncode
        == submanager.enums.ExitCode.ERROR_PARAMETERS.value
    )
    assert process_result.stderr.strip()
    assert not process_result.stdout.strip()
