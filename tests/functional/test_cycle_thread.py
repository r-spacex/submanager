"""Test that the cycle-thread command works as expected."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
from typing import (
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

# Third party imports
import pytest
from _pytest.mark.structures import (  # noqa: WPS436
    MarkDecorator,
)
from typing_extensions import (
    Final,
    Literal,
)

# Local imports
import submanager.exceptions
import submanager.models.config
from tests.functional.conftest import (
    CONFIG_PATHS_ONLINE,
    RunAndCheckCLICallable,
    apply_marks_to_param_configs,
)

# ---- Types ----

CycleConfigTuple = Tuple[
    List[str],
    str,
    Optional[
        Union[Type[submanager.exceptions.SubManagerUserError], Literal[False]]
    ],
    Optional[List[MarkDecorator]],
]


# ---- Constants ----

CYCLE_THREAD_COMMAND: Final[str] = "cycle-threads"

CYCLE_THREAD_KEY: Final[str] = "cycle_thread"
OTHER_THREAD_KEY: Final[str] = "new_thread"
PSEUDORANDOM_STRING: Final[str] = "izouashbutyzyep"


TEST_CONFIG_VAR_NAMES: Final[list[str]] = [
    "thread_keys",
    "check_text",
    "check_error",
]
TEST_IDS: Final[list[str]] = [
    "no_thread_keys",
    "one_invalid_thread_key",
    "mix_valid_invalid_thread_keys",
    "one_valid_thread_key",
    "multiple_valid_thread_keys",
]
TEST_CONFIGS: Final[list[CycleConfigTuple]] = [
    (
        [],
        "usage",
        False,
        None,
    ),
    (
        [PSEUDORANDOM_STRING],
        "not found in valid keys",
        submanager.exceptions.SubManagerUserError,
        None,
    ),
    (
        [CYCLE_THREAD_KEY, PSEUDORANDOM_STRING],
        "not found in valid keys",
        submanager.exceptions.SubManagerUserError,
        None,
    ),
    (
        [CYCLE_THREAD_KEY],
        "creating new thread",
        None,
        [pytest.mark.online, pytest.mark.slow],
    ),
    (
        [CYCLE_THREAD_KEY, OTHER_THREAD_KEY],
        "creating new thread",
        None,
        [pytest.mark.slow, pytest.mark.online],
    ),
]
TEST_CONFIGS_MARKED: Final = apply_marks_to_param_configs(TEST_CONFIGS)


# ---- Tests ----


@pytest.mark.parametrize(
    TEST_CONFIG_VAR_NAMES,
    TEST_CONFIGS_MARKED,
    ids=TEST_IDS,
)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ONLINE, indirect=True)
def test_cycle_thread(
    run_and_check_cli: RunAndCheckCLICallable,
    file_config: submanager.models.config.ConfigPaths,
    thread_keys: list[str],
    check_text: str,
    check_error: type[BaseException] | Literal[False] | None,
) -> None:
    """Test that running the get-config-info command doesn't break."""
    run_and_check_cli(
        cli_args=[CYCLE_THREAD_COMMAND, *thread_keys],
        config_paths=file_config,
        check_text=check_text,
        check_exits=bool(check_error) or check_error is False,
        check_code=(
            submanager.enums.ExitCode.ERROR_USER
            if check_error is not False
            else submanager.enums.ExitCode.ERROR_PARAMETERS
        ),
        check_error=check_error,
    )
