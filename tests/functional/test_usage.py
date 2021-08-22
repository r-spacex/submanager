"""Test that basic CLI usage is handled properly."""

# Future imports
from __future__ import (
    annotations,
)

# Third party imports
import pytest
from typing_extensions import (
    Final,
    Literal,
)

# Local imports
import submanager.enums
from tests.functional.conftest import (
    DEBUG_ARGS,
    RunAndCheckCLICallable,
)

# ---- Constants ----

HELP_COMMANDS: Final[list[str]] = ["-h", "--help"]
GOOD_COMMANDS: Final[list[str]] = ["--version"]
BAD_COMMANDS: Final[list[str]] = ["", " ", "--non-existent-cli-flag"]

CUSTOM_CONFIG_PATHS: Final[list[Literal[False] | None]] = [False, None]
CUSTOM_CONFIG_PATH_IDS: Final[list[str]] = ["default_paths", "custom_paths"]


# ---- Tests ----


@pytest.mark.parametrize("debug", DEBUG_ARGS)
@pytest.mark.parametrize(
    "custom_config_paths",
    CUSTOM_CONFIG_PATHS,
    ids=CUSTOM_CONFIG_PATH_IDS,
)
@pytest.mark.parametrize(
    "command",
    HELP_COMMANDS + GOOD_COMMANDS + BAD_COMMANDS,
)
def test_command_usage(
    run_and_check_cli: RunAndCheckCLICallable,
    command: str,
    custom_config_paths: Literal[False] | None,
    debug: str,
) -> None:
    """Test that the program handles good, bad and help commands properly."""
    check_exits = None
    check_code = None
    check_error: type[BaseException] | Literal[False] = False
    if command in HELP_COMMANDS:
        check_text = "help"
        check_exits = True
        check_code = submanager.enums.ExitCode.SUCCESS
    elif command in BAD_COMMANDS:
        check_text = "usage"
        check_code = submanager.enums.ExitCode.ERROR_PARAMETERS
        check_error = False if command else AttributeError
    elif command in GOOD_COMMANDS:
        check_text = command.replace("-", "").strip()
    else:
        raise ValueError(f"Command {command!r} not found in good, bad or help")

    run_and_check_cli(
        cli_args=[debug, command],
        config_paths=custom_config_paths,
        check_text=check_text,
        check_exits=check_exits,
        check_code=check_code,
        check_error=check_error,
    )
