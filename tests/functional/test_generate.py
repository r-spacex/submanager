"""Test that the generate-config command works as expected in the CLI."""

# Future imports
from __future__ import annotations

# Standard library imports
from pathlib import Path
from typing import (
    Any,
    Callable,  # Import from collections.abc in Python 3.9
    List,  # Not needed in Python 3.9
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
import submanager.core.initialization
import submanager.validation.validate
import submanager.enums
import submanager.exceptions
import submanager.models.config


# ---- Types ----

RunCLICallable = Callable[
    [List[str]], Tuple[CaptureResult[str], Optional[SystemExit]]]


# ---- Constants ----

GENERATE_COMMAND: Final[str] = "generate-config"


# ---- Helpers ----

def render_generate_args(config_path: Path, *args: str) -> list[str]:
    """Render the appropriate CLI args for the generate command."""
    args = tuple((arg for arg in args if arg))
    return ["--config-path", config_path.as_posix(), GENERATE_COMMAND, *args]


# ---- Tests ----

@pytest.mark.parametrize("exist_ok_arg", ["", "--exist-ok"])
@pytest.mark.parametrize("force_arg", ["", "--force"])
def test_config_doesnt_exist(
        run_cli: RunCLICallable,
        config_paths: submanager.models.config.ConfigPaths,
        force_arg: str,
        exist_ok_arg: str,
        ) -> None:
    """Test that the config file is generated when one doesn't exist."""
    cli_args = render_generate_args(
        config_paths.static, force_arg, exist_ok_arg)
    captured_output, captured_error = run_cli(cli_args)

    assert not captured_output.err.strip()
    assert not captured_error
    assert "generated" in captured_output.out.lower()
    assert config_paths.static.exists()
    submanager.core.initialization.setup_config(config_paths, verbose=True)


@pytest.mark.parametrize("exist_ok_arg", ["", "--exist-ok"])
def test_config_exists_force(
        run_cli: RunCLICallable,
        empty_config: submanager.models.config.ConfigPaths,
        exist_ok_arg: str,
        ) -> None:
    """Test that the config file is generated when one doesn't exist."""
    cli_args = render_generate_args(
        empty_config.static, "--force", exist_ok_arg)
    captured_output, captured_error = run_cli(cli_args)

    assert not captured_output.err.strip()
    assert not captured_error
    assert "overwritten" in captured_output.out.lower()
    assert empty_config.static.exists()
    submanager.core.initialization.setup_config(empty_config, verbose=True)


def test_config_exists_ok(
        run_cli: RunCLICallable,
        empty_config: submanager.models.config.ConfigPaths,
        ) -> None:
    """Test that no error occurs when the config exists and ok is passed."""
    cli_args = render_generate_args(empty_config.static, "--exist-ok")
    captured_output, captured_error = run_cli(cli_args)

    assert not captured_output.err.strip()
    assert "exists" in captured_output.out.lower()
    assert not captured_error


def test_config_exists_error(
        run_cli: RunCLICallable,
        empty_config: submanager.models.config.ConfigPaths,
        ) -> None:
    """Test that an error occurs when the configuration file exists."""
    cli_args = render_generate_args(empty_config.static)
    captured_output, captured_error = run_cli(cli_args)

    assert not captured_output.out.strip()
    assert "exists" in captured_output.err.lower()
    assert captured_error
    assert captured_error.code
    assert captured_error.code == submanager.enums.ExitCode.ERROR_USER.value
    assert isinstance(
        captured_error.__cause__, submanager.exceptions.ConfigExistsError)


@pytest.mark.parametrize("config_paths", ["xml", "ini", "txt"], indirect=True)
def test_generate_unknown_extension_error(
        run_cli: RunCLICallable,
        config_paths: submanager.models.config.ConfigPaths,
        ) -> None:
    """Test that generating a config file with an unknown extension errors."""
    cli_args = render_generate_args(config_paths.static)
    captured_output, captured_error = run_cli(cli_args)

    assert captured_error
    assert captured_error.code
    assert captured_error.code == submanager.enums.ExitCode.ERROR_USER.value
    assert isinstance(
        captured_error.__cause__, submanager.exceptions.ConfigTypeError)
    assert "format" in captured_output.err.lower()


def test_generated_config_validates_false(
        run_cli: RunCLICallable,
        config_paths: submanager.models.config.ConfigPaths,
        ) -> None:
    """Test that the generated config file validates successfully."""
    __: Any
    cli_args = render_generate_args(config_paths.static)
    __, captured_error = run_cli(cli_args)

    assert not captured_error
    with pytest.raises(submanager.exceptions.ConfigDefaultError):
        submanager.validation.validate.validate_config(
            config_paths=config_paths,
            offline_only=True,
            raise_error=True,
            verbose=True,
            )
    static_config, __ = submanager.core.initialization.setup_config(
        config_paths, verbose=True)
    with pytest.raises(submanager.exceptions.AccountConfigError):
        submanager.core.initialization.setup_accounts(
            static_config.accounts,
            config_path_refresh=config_paths.refresh,
            verbose=True,
            )
