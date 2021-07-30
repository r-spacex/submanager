"""Test that debug mode correctly suppresses errors in the CLI."""

# Future imports
from __future__ import annotations

# Standard library imports
from typing import (
    Callable,  # Import from collections.abc in Python 3.9
    Optional,  # Not needed in Python 3.10
    Sequence,  # Import from collections.abc in Python 3.9
    Tuple,  # Not needed in Python 3.9
    )

# Third party imports
import pytest
from _pytest.capture import CaptureResult
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )


# Local imports
import submanager.enums
import submanager.exceptions
import submanager.models.config


# ---- Types ----

RunCLIOutput = Tuple[CaptureResult[str], Optional[SystemExit]]
RunCLIPathsCallable = Callable[
    [submanager.models.config.ConfigPaths, Sequence[str]], RunCLIOutput]


# ---- Constants ----

VALIDATE_COMMAND: Final[str] = "validate-config"
MINIMAL_ARGS: Final[list[str]] = ["", "--minimal"]
INCLUDE_DISABLED_ARGS: Final[list[str]] = ["", "--include-disabled"]


# ---- Tests ----

@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("include_disabled", INCLUDE_DISABLED_ARGS)
def test_validate_generated_error(
        run_cli_paths: RunCLIPathsCallable,
        example_config: submanager.models.config.ConfigPaths,
        minimal: str,
        include_disabled: str,
        ) -> None:
    """Test that the config file is generated when one doesn't exist."""
    error_type: type[submanager.exceptions.SubManagerUserError]
    if minimal:
        error_type = submanager.exceptions.AccountConfigError
        error_text = "account"
    else:
        error_type = submanager.exceptions.ConfigDefaultError
        error_text = "default"

    captured_output, captured_error = run_cli_paths(
        example_config,
        [VALIDATE_COMMAND, "--offline-only", minimal, include_disabled],
        )

    assert error_text in captured_output.err.lower()
    assert captured_error
    assert captured_error.code
    assert captured_error.code == submanager.enums.ExitCode.ERROR_USER.value
    assert isinstance(captured_error.__cause__, error_type)
