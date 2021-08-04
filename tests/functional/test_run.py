"""Test that the run command works as expected."""

# Future imports
from __future__ import annotations

# Standard library imports
from typing import (
    Optional,  # Not needed in Python 3.9
    Tuple,  # Not needed in Python 3.9
    Type,  # Not needed in Python 3.9
    )

# Third party imports
import pytest
from _pytest.mark.structures import (
    MarkDecorator,
    )
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )

# Local imports
import submanager.exceptions
import submanager.models.config
from submanager.types import (
    ConfigDict,
    )
from tests.functional.conftest import (
    CONFIG_PATHS_ONLINE,
    RunAndCheckCLICallable,
    RunAndCheckDebugCallable,
    )


# ---- Types ----

RunConfigTuple = Tuple[
    ConfigDict,
    str,
    str,
    Optional[Type[submanager.exceptions.SubManagerUserError]],
    Optional[list[MarkDecorator]],
    ]


# ---- Constants ----

RUN_COMMAND: Final[str] = "run"
SKIP_VALIDATE_ARG: Final[str] = "--skip-validate"

TEST_RUN_CONFIGS: Final[list[RunConfigTuple]] = [
    (
        {"accounts": None},
        "",
        "account",
        submanager.exceptions.ConfigValidationError,
        None,
        ),
    (
        {"accounts": {"testbot": {"refresh_token": ""}}},
        "",
        "400",
        submanager.exceptions.ScopeCheckError,
        [pytest.mark.online],
        ),
    (
        {},
        "--skip-validate",
        "complet",
        None,
        [pytest.mark.online, pytest.mark.slow],
        ),
    ]
TEST_RUN_CONFIGS_MARKED: Final = [
    pytest.param(*config[:-1], marks=config[-1])
    if config[-1] is not None else config[:-1]
    for config in TEST_RUN_CONFIGS
    ]
TEST_RUN_IDS: Final[list[str]] = [
    "invalid_noskip_minimal",
    "invalid_noskip_validate",
    "valid_skipvalidate",
    ]


# ---- Tests ----

@pytest.mark.parametrize(
    "modified_config, skip_validate, check_text, check_error",
    TEST_RUN_CONFIGS_MARKED,
    ids=TEST_RUN_IDS,
    indirect=["modified_config"],
    )
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ONLINE, indirect=True)
def test_run(
        run_and_check_cli: RunAndCheckCLICallable,
        modified_config: submanager.models.config.ConfigPaths,
        skip_validate: str,
        check_text: str,
        check_error: type[BaseException] | None,
        ) -> None:
    """Test that the test configs validate true in offline mode."""
    run_and_check_cli(
        cli_args=[RUN_COMMAND, skip_validate],
        config_paths=modified_config,
        check_text=check_text,
        check_exits=bool(check_error),
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=check_error,
        )


def test_debug_validate(
        run_and_check_debug: RunAndCheckDebugCallable,
        ) -> None:
    """Test that --debug allows the error to bubble up and dump traceback."""
    run_and_check_debug([RUN_COMMAND])
