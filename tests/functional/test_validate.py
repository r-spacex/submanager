"""Test that the validate-config command correctly validates configuration."""

# Future imports
from __future__ import annotations

# Third party imports
import pytest
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )


# Local imports
import submanager.enums
import submanager.exceptions
import submanager.models.config
from tests.functional.conftest import (
    RunAndCheckCLICallable,
    )


# ---- Constants ----

VALIDATE_COMMAND: Final[str] = "validate-config"
MINIMAL_ARGS: Final[list[str]] = ["", "--minimal"]
INCLUDE_DISABLED_ARGS: Final[list[str]] = ["", "--include-disabled"]
OFFLINE_ONLY_ARG: Final[str] = "--offline-only"


# ---- Tests ----

@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("include_disabled", INCLUDE_DISABLED_ARGS)
def test_validate_generated_error(
        run_and_check_cli: RunAndCheckCLICallable,
        example_config: submanager.models.config.ConfigPaths,
        minimal: str,
        include_disabled: str,
        ) -> None:
    """Test that the generated config validates false."""
    error_type: type[submanager.exceptions.SubManagerUserError]
    if minimal:
        error_type = submanager.exceptions.AccountConfigError
    else:
        error_type = submanager.exceptions.ConfigDefaultError

    run_and_check_cli(
        VALIDATE_COMMAND,
        *[OFFLINE_ONLY_ARG, minimal, include_disabled],
        config_paths=example_config,
        check_text="account" if minimal else "default",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=error_type,
        )
