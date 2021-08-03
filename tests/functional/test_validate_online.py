"""Test that the validate-config command validates configuration online."""

# Future imports
from __future__ import annotations

# Third party imports
import pytest
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )

# Local imports
import submanager.models.config
from tests.functional.conftest import (
    CONFIG_PATHS_ONLINE,
    RunAndCheckCLICallable,
    )


# ---- Constants ----

VALIDATE_COMMAND: Final[str] = "validate-config"
OFFLINE_ONLY_ARGS: Final = [
    "--offline-only",
    pytest.param("", marks=[pytest.mark.slow, pytest.mark.online]),
    ]
INCLUDE_DISABLED_ARGS: Final[list[str]] = ["", "--include-disabled"]


# ---- Tests ----

@pytest.mark.parametrize("include_disabled", INCLUDE_DISABLED_ARGS)
@pytest.mark.parametrize("offline_only", OFFLINE_ONLY_ARGS)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ONLINE, indirect=True)
def test_valid_online(
        run_and_check_cli: RunAndCheckCLICallable,
        file_config: submanager.models.config.ConfigPaths,
        offline_only: str,
        include_disabled: str,
        ) -> None:
    """Test that the test configs validate true in offline mode."""
    should_fail = bool(include_disabled and not offline_only)
    run_and_check_cli(
        cli_args=[
            VALIDATE_COMMAND, offline_only, include_disabled],
        config_paths=file_config,
        check_text="permi" if should_fail else "succe",
        check_exits=should_fail,
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.WikiPagePermissionError,
        )
