"""Common functional test fixtures."""

# Future imports
from __future__ import annotations

# Standard library imports
import subprocess
import sys
from pathlib import Path
from typing import (
    Callable,  # Import from collections.abc in Python 3.9
    TypeVar,
    Tuple,  # Not needed in Python 3.9
    Optional,  # Not needed in Python 3.10
    )

# Third party imports
import pytest
from _pytest.capture import (
    CaptureResult,
    )
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )

# Local imports
import submanager.cli
import submanager.config.static
import submanager.models.config


# ---- Types ----

ArgType = TypeVar("ArgType")
RunCLIOutput = Tuple[CaptureResult[str], Optional[SystemExit]]


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

CONFIG_EXTENSIONS: Final[list[str]] = ["toml"]


# ---- Fixtures ----

@pytest.fixture
def run_cli(
        capfd: pytest.CaptureFixture[str],
        ) -> Callable[[list[str]], RunCLIOutput]:
    """Run the package CLI with the passed argument(s)."""
    def _run_cli(
            cli_args: list[str]) -> RunCLIOutput:
        captured_error = None
        try:
            submanager.cli.main(cli_args)
        except SystemExit as error:
            captured_error = error
        captured_output = capfd.readouterr()
        return captured_output, captured_error
    return _run_cli


@pytest.fixture(params=INVOCATION_METHODS, ids=INVOCATION_IDS)
def invoke_command(
        request: pytest.FixtureRequest,
        ) -> Callable[[str], subprocess.CompletedProcess[str]]:
    """Invoke the passed command with a given invocation."""
    def _invoke_command(command: str) -> subprocess.CompletedProcess[str]:
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


@pytest.fixture(name="config_paths", params=CONFIG_EXTENSIONS)
def fixture_config_paths(
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
        config_paths: submanager.models.config.ConfigPaths,
        ) -> submanager.models.config.ConfigPaths:
    """Generate an empty config file in a temp directory."""
    with open(config_paths.static, mode="w",
              encoding="utf-8", newline="\n") as static_config_file:
        static_config_file.write("\n")
    return config_paths


@pytest.fixture
def example_config(
        config_paths: submanager.models.config.ConfigPaths,
        ) -> submanager.models.config.ConfigPaths:
    """Generate an example config file in a temp directory."""
    submanager.config.static.generate_static_config(config_paths.static)
    return config_paths
