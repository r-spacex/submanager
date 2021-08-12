"""Test that the run command works as expected."""

# Future imports
from __future__ import annotations

# Standard library imports
from typing import (
    List,  # Not needed in Python 3.9
    Optional,  # Not needed in Python 3.10
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
    List[str],
    List[str],
    str,
    Optional[Type[submanager.exceptions.SubManagerUserError]],
    Optional[List[MarkDecorator]],
]


# ---- Constants ----

PSEUDORANDOM_STRING: Final[str] = "izouashbutyzyep"

RUN_COMMAND: Final[str] = "run"
START_COMMAND: Final[str] = "start"
COMMANDS: Final[list[str]] = [RUN_COMMAND, START_COMMAND]

SKIP_VALIDATE_ARG: Final[str] = "--skip-validate"
RESYNC_ALL_ARG: Final[str] = "--resync-all"
REPEAT_INTERVAL_S_ARG: Final[str] = "--repeat-interval-s"
REPEAT_MAX_N_ARG: Final[str] = "--repeat-max-n"


TEST_CONFIG_VAR_NAMES: Final[list[str]] = [
    "modified_config",
    "cli_args_run",
    "cli_args_start",
    "check_text",
    "check_error",
]
TEST_CONFIGS: Final[list[RunConfigTuple]] = [
    (
        {"accounts": None},
        [],
        [],
        "account",
        submanager.exceptions.ConfigValidationError,
        None,
    ),
    (
        {
            "accounts": {
                "testbot": {"config": {"client_id": PSEUDORANDOM_STRING}}
            }
        },
        [],
        [REPEAT_MAX_N_ARG, "1"],
        "scope",
        submanager.exceptions.ScopeCheckError,
        [pytest.mark.online],
    ),
    (
        {},
        [SKIP_VALIDATE_ARG, RESYNC_ALL_ARG],
        [SKIP_VALIDATE_ARG, REPEAT_INTERVAL_S_ARG, "5", REPEAT_MAX_N_ARG, "2"],
        "complet",
        None,
        [pytest.mark.online, pytest.mark.slow],
    ),
]
TEST_CONFIGS_MARKED: Final = [
    pytest.param(*config[:-1], marks=config[-1])
    if config[-1] is not None
    else config[:-1]
    for config in TEST_CONFIGS
]
TEST_IDS: Final[list[str]] = [
    "invalid_noskip_minimal",
    "invalid_noskip_validate",
    "valid_skipvalidate",
]


# ---- Tests ----


@pytest.mark.parametrize(
    TEST_CONFIG_VAR_NAMES,
    TEST_CONFIGS_MARKED,
    ids=TEST_IDS,
    indirect=["modified_config"],
)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ONLINE, indirect=True)
@pytest.mark.parametrize("command", COMMANDS)
def test_start_run(
    run_and_check_cli: RunAndCheckCLICallable,
    modified_config: submanager.models.config.ConfigPaths,
    command: str,
    cli_args_run: list[str],
    cli_args_start: list[str],
    check_text: str,
    check_error: type[BaseException] | None,
) -> None:
    """Test that the test configs validate true in offline mode."""
    if command == "run":
        cli_args = cli_args_run
    elif command == "start":
        cli_args = cli_args_start
    else:
        raise ValueError("Command must be run or start")

    run_and_check_cli(
        cli_args=[command, *cli_args],
        config_paths=modified_config,
        check_text=check_text,
        check_exits=bool(check_error),
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=check_error,
    )


@pytest.mark.parametrize("command", COMMANDS)
def test_debug_error(
    run_and_check_debug: RunAndCheckDebugCallable,
    command: str,
) -> None:
    """Test that --debug allows the error to bubble up and dump traceback."""
    run_and_check_debug([command])
