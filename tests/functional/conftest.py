"""Common functional test fixtures."""

# Future imports
from __future__ import annotations

# Standard library imports
import subprocess
import sys
from pathlib import Path
from typing import (
    Any,
    Callable,  # Import from collections.abc in Python 3.9
    Optional,  # Not needed in Python 3.9
    Sequence,  # Import from collections.abc in Python 3.9
    Tuple,  # Not needed in Python 3.9
    Type,  # Not needed in Python 3.9
    TypeVar,
    Union,  # Not needed in Python 3.10
    )

# Third party imports
import pytest
from _pytest.capture import (
    CaptureResult,
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
            command: str,
            *cli_args: str,
            config_paths: ConfigPathValues = None,
            check_text: str | None = None,
            check_exits: bool | None = None,
            check_code: submanager.enums.ExitCode | None = None,
            check_error: CheckErrorValues = None,
            ) -> RunCLIOutput:
        """Call the run and check CLI fixture function."""


# Invoke command types

InvokeOutput = subprocess.CompletedProcess[str]
InvokeCommandCallable = Callable[[str], InvokeOutput]


# ---- Constants ----

PACKAGE_NAME: Final[str] = "submanager"
ENTRYPOINT_NAME: Final[str] = PACKAGE_NAME

INVOCATION_RUNPY: Final[list[str]] = [
    sys.executable, "-b", "-X", "dev", "-m", PACKAGE_NAME]
INVOCATION_IDS: Final[list[str]] = [
    "entrypoint",
    "runpy",
    ]
INVOCATION_METHODS: Final[list[list[str]]] = [
    [ENTRYPOINT_NAME],
    INVOCATION_RUNPY,
    ]

CONFIG_EXTENSIONS_GOOD: Final[list[str]] = ["toml", "json"]
CONFIG_EXTENSIONS_GOOD_GENERATE: Final[list[str]] = ["toml"]
CONFIG_EXTENSIONS_BAD: Final[list[str]] = ["xml", "ini", "txt"]


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
            command: str,
            *cli_args: str,
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
        captured_output, captured_error = run_cli_paths(
            [command, *cli_args], config_paths)

        # Check output text
        if check_text:
            if check_exits and check_code and check_code.value:
                assert check_text in captured_output.err.lower()
            else:
                assert check_text in captured_output.out.lower()
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


@pytest.fixture(
    name="temp_config_paths", params=CONFIG_EXTENSIONS_GOOD_GENERATE)
def fixture_temp_config_paths(
        request: pytest.FixtureRequest,
        tmp_path: Path,
        ) -> submanager.models.config.ConfigPaths:
    """Generate a set of temporary ConfigPaths."""
    config_extension: str = request.param  # type: ignore[attr-defined]
    config_paths = submanager.models.config.ConfigPaths(
        static=tmp_path / f"temp_config_static.{config_extension}",
        dynamic=tmp_path / "temp_config_dynamic.json",
        refresh=tmp_path / "refresh" / "refresh_token_{key}.txt",
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
