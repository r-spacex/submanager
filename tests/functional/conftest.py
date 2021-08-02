"""Common functional test fixtures."""

# Future imports
from __future__ import annotations

# Standard library imports
import shutil
import subprocess
import sys
from pathlib import Path
from typing import (
    Any,
    Callable,  # Import from collections.abc in Python 3.9
    Collection,  # Import from collections.abc in Python 3.9
    Mapping,  # Import from collections.abc in Python 3.9
    MutableMapping,  # Import from collections.abc in Python 3.9
    Optional,  # Not needed in Python 3.9
    Sequence,  # Import from collections.abc in Python 3.9
    Tuple,  # Not needed in Python 3.9
    Type,  # Not needed in Python 3.9
    TYPE_CHECKING,  # Not needed in Python 3.9
    TypeVar,
    Union,  # Not needed in Python 3.10
    )

# Third party imports
import pytest
from _pytest.capture import (
    CaptureResult,
    )
from _pytest.config import (
    Config,
    )
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    Literal,  # Added to typing in Python 3.8
    Protocol,  # Added to typing in Python 3.8
    )

# Local imports
import submanager.cli
import submanager.config.static
import submanager.config.utils
import submanager.enums
import submanager.models.config
import submanager.utils.misc
from submanager.types import (
    ConfigDict,
    )


# ---- Types ----

# General types

ArgType = TypeVar("ArgType")


# Run CLI types

ConfigPathValues = Union[
    submanager.models.config.ConfigPaths, Literal[False], None]
CheckErrorValues = Union[Type[BaseException], Literal[False], None]

RunCLIOutput = Tuple[CaptureResult[str], Optional[SystemExit]]
RunCLICallable = Callable[[Sequence[str]], RunCLIOutput]
RunCLIPathsCallable = (Callable[
    [Sequence[str], Union[
        submanager.models.config.ConfigPaths, Literal[False]]], RunCLIOutput])


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

# Package constants
PACKAGE_NAME: Final[str] = "submanager"
ENTRYPOINT_NAME: Final[str] = PACKAGE_NAME

# Argument constants
DEBUG_ARGS: Final[list[str]] = ["", "--debug"]

# Invocation constants
INVOCATION_RUNPY: Final[list[str]] = [
    sys.executable, "-b", "-X", "dev", "-m", PACKAGE_NAME]
INVOCATION_METHODS: Final[list[list[str]]] = [
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
DATA_DIR: Final[Path] = Path(__file__).parent / "data"
RSPACEX_CONFIG_PATH: Final[Path] = DATA_DIR / "rspacex.toml"
TECHNICAL_CONFIG_PATH: Final[Path] = DATA_DIR / "sxtechnical.toml"
CONFIG_PATHS_ALL: Final[list[Path]] = [
    RSPACEX_CONFIG_PATH, TECHNICAL_CONFIG_PATH]


# ---- Hooks ----

def pytest_make_parametrize_id(
        config: Config,  # pylint: disable = unused-argument
        val: object,
        argname: str,  # pylint: disable = unused-argument
        ) -> str | None:
    """Intelligently generate parameter IDs; hook for pytest."""
    val_id: object = val
    if not isinstance(val, (str, bytes)):
        val_name: object = getattr(val, "name", None)
        if isinstance(val, Path):
            val_id = val.stem
        # static analysis: ignore[non_boolean_in_boolean_context]
        elif val_name and isinstance(val_name, str):
            val_id = val_name
        elif isinstance(val, Collection):
            if isinstance(val, Mapping):
                # static analysis: ignore[undefined_attribute]
                val_iter = iter(val.values())
            else:
                val_iter = iter(val)
            # static analysis: ignore[incompatible_argument]
            if len(val) == 1:
                val_id = next(val_iter)
            elif all((isinstance(val_item, str) for val_item in val_iter)):
                # static analysis: ignore[incompatible_argument]
                val_id = " ".join(val)

    if isinstance(val_id, bytes):
        return val_id.decode()
    if isinstance(val_id, str):
        return val_id.strip().strip("-").replace("-", "")
    if val_id is None or isinstance(val_id, (int, float, complex, bool)):
        return str(val_id)

    return None


# ---- Fixtures ----

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
            config_paths: (
                submanager.models.config.ConfigPaths | Literal[False]),
            ) -> RunCLIOutput:
        config_path_args = []
        if config_paths:
            config_path_args = [
                "--config-path",
                config_paths.static.as_posix(),
                "--dynamic-config-path",
                config_paths.dynamic.as_posix(),
                "--refresh-config-path",
                config_paths.refresh.as_posix(),
                ]
        all_cli_args = [*config_path_args, *cli_args]
        return run_cli(all_cli_args)
    return _run_cli_paths


@pytest.fixture
def run_and_check_cli(
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
                (check_code and check_code.value) or check_error)

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


@pytest.fixture(params=INVOCATION_METHODS, ids=INVOCATION_IDS)
def invoke_command(
        request: pytest.FixtureRequest,
        ) -> InvokeCommandCallable:
    """Invoke the passed command with a given invocation."""
    def _invoke_command(command: str) -> InvokeOutput:
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


@pytest.fixture(name="temp_config_dir")
def fixture_temp_config_dir(
        request: pytest.FixtureRequest,
        tmp_path: Path,
        ) -> Path:
    """Generate a set of temporary ConfigPaths."""
    config_sub_dir: Path | str | None = getattr(request, "param", None)
    if not config_sub_dir:
        return tmp_path
    return tmp_path / config_sub_dir


@pytest.fixture(
    name="temp_config_paths", params=CONFIG_EXTENSIONS_GOOD_GENERATE)
def fixture_temp_config_paths(
        request: pytest.FixtureRequest,
        temp_config_dir: Path,
        ) -> submanager.models.config.ConfigPaths:
    """Generate a set of temporary ConfigPaths."""
    config_extension: str = request.param  # type: ignore[attr-defined]
    config_paths = submanager.models.config.ConfigPaths(
        static=temp_config_dir / f"temp_config_static.{config_extension}",
        dynamic=temp_config_dir / "temp_config_dynamic.json",
        refresh=temp_config_dir / "refresh" / "refresh_token_{key}.txt",
        )
    return config_paths


@pytest.fixture
def empty_config(
        temp_config_paths: submanager.models.config.ConfigPaths,
        ) -> submanager.models.config.ConfigPaths:
    """Generate an empty config file in a temp directory."""
    with open(temp_config_paths.static, mode="w",
              encoding="utf-8", newline="\n") as static_config_file:
        static_config_file.write("\n")
    return temp_config_paths


@pytest.fixture
def list_config(
        temp_config_paths: submanager.models.config.ConfigPaths,
        ) -> submanager.models.config.ConfigPaths:
    """Generate a list config file in a temp directory."""
    config_data: Any = ["spam", "eggs"]
    submanager.config.utils.write_config(
        config_data, config_path=temp_config_paths.static)
    return temp_config_paths


@pytest.fixture
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
    source_path: object = getattr(request, "param", None)
    # static analysis: ignore[non_boolean_in_boolean_context]
    if not source_path:
        raise ValueError("Source path must be passed via request param")
    if not isinstance(source_path, (Path, str)):
        raise TypeError(f"Source path {source_path!r} must be Path or str, "
                        f"not {type(source_path)!r}")
    shutil.copyfile(source_path, temp_config_paths.static)
    return temp_config_paths


@pytest.fixture
def modified_config(
        file_config: submanager.models.config.ConfigPaths,
        request: pytest.FixtureRequest,
        ) -> submanager.models.config.ConfigPaths:
    """Modify an existing config file and return the path."""
    update_dict: ConfigDict | None = getattr(request, "param", None)
    if update_dict is None:
        raise ValueError("Update dict must be passed via request param")
    if not isinstance(update_dict, MutableMapping):
        raise TypeError(f"Update dict {update_dict!r} must be a mapping, "
                        f"not {type(update_dict)!r}")

    config_data = submanager.config.utils.load_config(file_config.static)
    config_data_modified = submanager.utils.misc.update_dict_recursive(
        base=dict(config_data),
        update=dict(update_dict),
        inplace=False,
        )
    submanager.config.utils.write_config(
        config_data_modified, config_path=file_config.static)

    return file_config
