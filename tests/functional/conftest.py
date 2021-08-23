"""Common functional test fixtures."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import copy
import shutil
import subprocess  # nosec
import sys
from pathlib import (
    Path,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

# Third party imports
import pytest
from _pytest.capture import (  # noqa: WPS436
    CaptureResult,
)
from typing_extensions import (
    Final,
    Literal,
    Protocol,
)

# Local imports
import submanager.cli
import submanager.config.static
import submanager.config.utils
import submanager.enums
import submanager.models.config
import submanager.utils.dicthelpers
from tests.conftest import (
    PACKAGE_NAME,
)

# ---- Types ----

# General types

ArgType = TypeVar("ArgType")

ArgList = List[str]


# Run CLI types

ConfigPathValues = Union[
    submanager.models.config.ConfigPaths,
    Literal[False],
    None,
]
CheckErrorValues = Union[Type[BaseException], Literal[False], None]

RunCLIOutput = Tuple[CaptureResult[str], Optional[SystemExit]]
RunCLICallable = Callable[[Sequence[str]], RunCLIOutput]
RunCLIPathsCallable = Callable[
    [
        Sequence[str],
        Union[submanager.models.config.ConfigPaths, Literal[False]],
    ],
    RunCLIOutput,
]

RunAndCheckDebugCallable = Callable[[Sequence[str]], None]


class RunAndCheckCLICallable(Protocol):
    """Callable class for the run and check CLI fixture function."""

    def __call__(  # static analysis: ignore[incompatible_return_value]
        self,
        cli_args: Sequence[str],
        config_paths: ConfigPathValues = None,
        check_text: str | None = None,
        check_exits: bool | None = None,
        check_code: submanager.enums.ExitCode | None = None,
        check_error: CheckErrorValues = None,
    ) -> RunCLIOutput:
        """Call the run and check CLI fixture function."""


# Invoke command types

if TYPE_CHECKING:
    # pylint: disable = unsubscriptable-object, useless-suppression
    InvokeOutput = subprocess.CompletedProcess[str]
else:
    InvokeOutput = subprocess.CompletedProcess

InvokeCommandCallable = Callable[[str], InvokeOutput]


# ---- Constants ----

PARAM_ATTR: Final[str] = "param"

# Argument constants
DEBUG_ARGS: Final[ArgList] = ["", "--debug"]

# Invocation constants
ENTRYPOINT_NAME: Final[str] = PACKAGE_NAME
INVOCATION_RUNPY: Final[ArgList] = [
    sys.executable,
    "-b",
    "-X",
    "dev",
    "-m",
    PACKAGE_NAME,
]
INVOCATION_METHODS: Final[list[ArgList]] = [
    [ENTRYPOINT_NAME],
    INVOCATION_RUNPY,
]
INVOCATION_IDS: Final[list[str]] = [
    "entrypoint",
    "runpy",
]

# Extension constants
CONFIG_EXTENSIONS_GOOD: Final[list[str]] = ["toml", "json"]
CONFIG_EXTENSIONS_GOOD_GENERATE: Final[list[str]] = ["toml"]
CONFIG_EXTENSIONS_BAD: Final[list[str]] = ["xml", "ini", "txt"]

# Path constants
CONFIG_DATA_DIR: Final[Path] = Path(__file__).parent / "data"

RSPACEX_CONFIG_PATH: Final[Path] = CONFIG_DATA_DIR / "rspacex.toml"
TECHNICAL_CONFIG_PATH: Final[Path] = CONFIG_DATA_DIR / "sxtechnical.toml"
ONLINE_CONFIG_PATH: Final[Path] = CONFIG_DATA_DIR / "online.toml"

CONFIG_PATHS_OFFLINE: Final[list[Path]] = [
    RSPACEX_CONFIG_PATH,
    TECHNICAL_CONFIG_PATH,
]
CONFIG_PATHS_ONLINE: Final[list[Path]] = [ONLINE_CONFIG_PATH]
CONFIG_PATHS_ALL: Final[list[Path]] = (
    CONFIG_PATHS_OFFLINE + CONFIG_PATHS_ONLINE
)


# ---- Parameter helper functions ----


def apply_marks_to_param_configs(
    param_configs: Sequence[tuple[Any, ...]],
) -> list[tuple[Any, ...]]:
    """Apply the marks given as the last element in a tuple to the configs."""
    param_configs_marked = [
        pytest.param(*config[:-1], marks=config[-1])
        if config[-1] is not None
        else config[:-1]
        for config in param_configs
    ]
    return param_configs_marked


# ---- Test helper fixtures ----


@pytest.fixture(name="run_cli")
def fixture_run_cli(capfd: pytest.CaptureFixture[str]) -> RunCLICallable:
    """Run the package CLI with the passed argument(s)."""

    def _run_cli(
        cli_args: Sequence[str],
    ) -> RunCLIOutput:
        cli_args = [arg for arg in cli_args if arg]
        captured_error = None
        try:
            submanager.cli.main(cli_args)
        except SystemExit as error:
            captured_error = error
        captured_output = capfd.readouterr()
        return captured_output, captured_error

    return _run_cli


@pytest.fixture(name="run_cli_paths")
def fixture_run_cli_paths(
    run_cli: RunCLICallable,
) -> RunCLIPathsCallable:
    """Run the package CLI with the passed argument(s)."""

    def _run_cli_paths(
        cli_args: Sequence[str],
        config_paths: (submanager.models.config.ConfigPaths | Literal[False]),
    ) -> RunCLIOutput:
        config_path_args = []
        if config_paths:
            config_path_args = [
                "--config-path",
                config_paths.static.as_posix(),
                "--dynamic-config-path",
                config_paths.dynamic.as_posix(),
            ]
        all_cli_args = [*config_path_args, *cli_args]
        return run_cli(all_cli_args)

    return _run_cli_paths


@pytest.fixture(name="run_and_check_cli")  # noqa: WPS231
def fixture_run_and_check_cli(  # noqa: WPS231
    run_cli_paths: RunCLIPathsCallable,
    temp_config_paths: submanager.models.config.ConfigPaths,
) -> RunAndCheckCLICallable:
    """Run the package CLI and perform various checks on the output."""

    def _run_and_check_cli(
        cli_args: Sequence[str],
        config_paths: ConfigPathValues = None,
        check_text: str | None = None,
        check_exits: bool | None = None,
        check_code: submanager.enums.ExitCode | None = None,
        check_error: CheckErrorValues = None,
    ) -> RunCLIOutput:
        # Automatically set up exit check and config paths if needed
        if config_paths is None:
            config_paths = temp_config_paths
        if check_exits is None:
            check_exits = bool(
                (check_code and check_code.value) or check_error,
            )

        # Run CLI command
        captured_output, captured_error = run_cli_paths(cli_args, config_paths)

        # Check output text
        if check_text:
            if check_exits and check_code and check_code.value:
                assert check_text.strip() in captured_output.err.lower()
            else:
                assert check_text.strip() in captured_output.out.lower()
                assert not captured_output.err.strip()

        # Check output error
        if not captured_error:
            assert not check_exits
        else:
            assert check_exits
            if check_code is not None:
                assert captured_error.code == check_code.value
            if check_error is not None:
                if check_error:
                    assert isinstance(captured_error.__cause__, check_error)
                else:
                    assert not getattr(captured_error, "__cause__", None)

        return captured_output, captured_error

    return _run_and_check_cli


@pytest.fixture(params=DEBUG_ARGS)
def run_and_check_debug(
    run_and_check_cli: RunAndCheckCLICallable,
    temp_config_paths: submanager.models.config.ConfigPaths,
    request: pytest.FixtureRequest,
) -> RunAndCheckDebugCallable:
    """Test that --debug allows the error to bubble up and dump traceback."""
    check_text = "not found"
    check_error = submanager.exceptions.ConfigNotFoundError
    debug: str = getattr(request, PARAM_ATTR, "")

    def _test_debug_error(cli_args: Sequence[str]) -> None:
        try:
            run_and_check_cli(
                cli_args=[debug, *cli_args],
                config_paths=temp_config_paths,
                check_text=check_text,
                check_code=submanager.enums.ExitCode.ERROR_USER,
                check_error=check_error,
            )
        except submanager.exceptions.SubManagerUserError as error:
            if not debug:
                raise
            assert isinstance(error, check_error)
            assert check_text in str(error)
        else:
            assert not debug

    return _test_debug_error


@pytest.fixture(params=INVOCATION_METHODS, ids=INVOCATION_IDS)
def invoke_command(
    request: pytest.FixtureRequest,
) -> InvokeCommandCallable:
    """Invoke the passed command with a given invocation."""

    def _invoke_command(command: str) -> InvokeOutput:
        invocation: ArgList = request.param  # type: ignore[attr-defined]
        process_result = subprocess.run(
            invocation + [command],
            capture_output=True,
            check=False,
            encoding="utf-8",
            text=True,
        )
        return process_result

    return _invoke_command


# ---- Setup fixtures ----


@pytest.fixture(name="temp_config_dir")
def fixture_temp_config_dir(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Path:
    """Generate a set of temporary ConfigPaths."""
    config_sub_dir: Path | str | None = getattr(request, PARAM_ATTR, None)
    if not config_sub_dir:
        return tmp_path
    return tmp_path / config_sub_dir


@pytest.fixture(
    name="temp_config_paths",
    params=CONFIG_EXTENSIONS_GOOD_GENERATE,
)
def fixture_temp_config_paths(
    request: pytest.FixtureRequest,
    temp_config_dir: Path,
) -> submanager.models.config.ConfigPaths:
    """Generate a set of temporary ConfigPaths."""
    config_extension: str = request.param  # type: ignore[attr-defined]
    config_paths = submanager.models.config.ConfigPaths(
        static=temp_config_dir / f"temp_config_static.{config_extension}",
        dynamic=temp_config_dir / "temp_config_dynamic.json",
    )
    return config_paths


@pytest.fixture()
def empty_config(
    temp_config_paths: submanager.models.config.ConfigPaths,
) -> submanager.models.config.ConfigPaths:
    """Generate an empty config file in a temp directory."""
    with open(
        temp_config_paths.static,
        mode="w",
        encoding="utf-8",
        newline="\n",
    ) as static_config_file:
        static_config_file.write("\n")
    return temp_config_paths


@pytest.fixture()
def list_config(
    temp_config_paths: submanager.models.config.ConfigPaths,
) -> submanager.models.config.ConfigPaths:
    """Generate a list config file in a temp directory."""
    config_data: Any = ["spam", "eggs"]
    submanager.config.utils.write_config(
        config_data,
        config_path=temp_config_paths.static,
    )
    return temp_config_paths


@pytest.fixture()
def example_config(
    temp_config_paths: submanager.models.config.ConfigPaths,
) -> submanager.models.config.ConfigPaths:
    """Generate an example config file in a temp directory."""
    submanager.config.static.generate_static_config(temp_config_paths.static)
    return temp_config_paths


@pytest.fixture(name="file_config")
def fixture_file_config(
    temp_config_paths: submanager.models.config.ConfigPaths,
    request: pytest.FixtureRequest,
) -> submanager.models.config.ConfigPaths:
    """Use a config file from the test data directory."""
    source_path: object = getattr(request, PARAM_ATTR, None)
    # static analysis: ignore[non_boolean_in_boolean_context]
    if not source_path:
        raise ValueError("Source path must be passed via request param")
    if not isinstance(source_path, (Path, str)):
        raise TypeError(
            f"Source path {source_path!r} must be Path or str, "
            f"not {type(source_path)!r}",
        )
    shutil.copyfile(source_path, temp_config_paths.static)
    return temp_config_paths


@pytest.fixture()
def modified_config(
    file_config: submanager.models.config.ConfigPaths,
    request: pytest.FixtureRequest,
) -> submanager.models.config.ConfigPaths:
    """Modify an existing config file and return the path."""
    # Get and check request params
    request_param = getattr(request, PARAM_ATTR, None)
    if request_param is None:
        raise ValueError("Update dict must be passed via request param")
    if isinstance(request_param, Sequence):
        update_dict, disable_all = request_param
    else:
        update_dict = request_param
        disable_all = False
    if not isinstance(update_dict, MutableMapping):
        raise TypeError(
            f"Update dict {update_dict!r} must be a mapping, "
            f"not {type(update_dict)!r}",
        )

    # Disable all items if requested
    config_data = submanager.config.utils.load_config(file_config.static)
    if disable_all:
        config_data_modified = (
            submanager.utils.dicthelpers.process_items_recursive(
                dict(config_data),
                fn_torun=lambda value: False,
                keys_match={"enabled"},
                inplace=False,
            )
        )
        if isinstance(disable_all, str):
            config_data_level = config_data_modified
            for key in disable_all.split("."):
                config_data_level = config_data_level[key]
                if config_data_level.get("enabled", None) is not None:
                    config_data_level["enabled"] = True
    else:
        config_data_modified = copy.deepcopy(dict(config_data))

    # Modify config and write it back
    config_data_modified = submanager.utils.dicthelpers.update_recursive(
        base=config_data_modified,
        update=dict(update_dict),
        inplace=False,
    )
    submanager.config.utils.write_config(
        config_data_modified,
        config_path=file_config.static,
    )

    return file_config
