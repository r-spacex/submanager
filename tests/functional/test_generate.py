"""Test that the generate-config command works as expected in the CLI."""

# Future imports
from __future__ import annotations

# Standard library imports
from typing import (
    Any,
    Callable,  # Import from collections.abc in Python 3.9
    Optional,  # Not needed in Python 3.10
    Sequence,  # Import from collections.abc in Python 3.9
    Tuple,  # Not needed in Python 3.9
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

RunCLIOutput = Tuple[CaptureResult[str], Optional[SystemExit]]
RunCLIPathsCallable = Callable[
    [submanager.models.config.ConfigPaths, Sequence[str]], RunCLIOutput]


# ---- Constants ----

GENERATE_COMMAND: Final[str] = "generate-config"
FORCE_ARGS: Final[list[str]] = ["", "--force"]
EXIST_OK_ARGS: Final[list[str]] = ["", "--exist-ok"]


# ---- Tests ----

@pytest.mark.parametrize("exist_ok", EXIST_OK_ARGS)
@pytest.mark.parametrize("force", FORCE_ARGS)
def test_config_doesnt_exist(
        run_cli_paths: RunCLIPathsCallable,
        config_paths: submanager.models.config.ConfigPaths,
        force: str,
        exist_ok: str,
        ) -> None:
    """Test that the config file is generated when one doesn't exist."""
    captured_output, captured_error = run_cli_paths(
        config_paths, [GENERATE_COMMAND, force, exist_ok])

    assert not captured_output.err.strip()
    assert not captured_error
    assert "generated" in captured_output.out.lower()
    assert config_paths.static.exists()
    submanager.core.initialization.setup_config(config_paths, verbose=True)


@pytest.mark.parametrize("exist_ok", EXIST_OK_ARGS)
@pytest.mark.parametrize("force", FORCE_ARGS)
def test_config_exists(
        run_cli_paths: RunCLIPathsCallable,
        empty_config: submanager.models.config.ConfigPaths,
        force: str,
        exist_ok: str,
        ) -> None:
    """Test that the config file is generated when one doesn't exist."""
    if force:
        output_text = "overwritten"
    else:
        output_text = "exists"

    captured_output, captured_error = run_cli_paths(
        empty_config, [GENERATE_COMMAND, force, exist_ok])

    if force or exist_ok:
        assert not captured_output.err.strip()
        assert output_text in captured_output.out.lower()
        assert not captured_error
        if force:
            assert empty_config.static.exists()
            submanager.core.initialization.setup_config(
                empty_config, verbose=True)
    else:
        assert not captured_output.out.strip()
        assert output_text in captured_output.err.lower()
        assert captured_error
        assert captured_error.code
        assert (
            captured_error.code == submanager.enums.ExitCode.ERROR_USER.value)
        assert isinstance(
            captured_error.__cause__, submanager.exceptions.ConfigExistsError)


@pytest.mark.parametrize("config_paths", ["xml", "ini", "txt"], indirect=True)
def test_generate_unknown_extension_error(
        run_cli_paths: RunCLIPathsCallable,
        config_paths: submanager.models.config.ConfigPaths,
        ) -> None:
    """Test that generating a config file with an unknown extension errors."""
    captured_output, captured_error = run_cli_paths(
        config_paths, [GENERATE_COMMAND])

    assert captured_error
    assert captured_error.code
    assert captured_error.code == submanager.enums.ExitCode.ERROR_USER.value
    assert isinstance(
        captured_error.__cause__, submanager.exceptions.ConfigTypeError)
    assert "format" in captured_output.err.lower()


def test_generated_config_validates_false(
        run_cli_paths: RunCLIPathsCallable,
        config_paths: submanager.models.config.ConfigPaths,
        ) -> None:
    """Test that the generated config file validates successfully."""
    __: Any
    __, captured_error = run_cli_paths(
        config_paths, [GENERATE_COMMAND])

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
