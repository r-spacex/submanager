"""Test that the validate-config command correctly validates configuration."""

# Future imports
from __future__ import annotations

# Third party imports
import pytest
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )


# Local imports
import submanager.enums
import submanager.exceptions
import submanager.models.config
from tests.functional.conftest import (
    CONFIG_EXTENSIONS_BAD,
    CONFIG_EXTENSIONS_GOOD,
    RunAndCheckCLICallable,
    )


# ---- Constants ----

VALIDATE_COMMAND: Final[str] = "validate-config"
OFFLINE_ONLY_ARG: Final[str] = "--offline-only"

MINIMAL_ARGS: Final[list[str]] = ["", "--minimal"]
INCLUDE_DISABLED_ARGS: Final[list[str]] = ["", "--include-disabled"]


# ---- Tests ----

@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("include_disabled", INCLUDE_DISABLED_ARGS)
def test_validate_generated_error(
        run_and_check_cli: RunAndCheckCLICallable,
        example_config: submanager.models.config.ConfigPaths,
        minimal: str,
        include_disabled: str,
        ) -> None:
    """Test that the generated config validates false."""
    error_type: type[submanager.exceptions.SubManagerUserError]
    if minimal:
        error_type = submanager.exceptions.AccountConfigError
    else:
        error_type = submanager.exceptions.ConfigDefaultError

    run_and_check_cli(
        VALIDATE_COMMAND,
        *[OFFLINE_ONLY_ARG, minimal, include_disabled],
        config_paths=example_config,
        check_text="account" if minimal else "default",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=error_type,
        )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("temp_config_dir", ["", "missing_dir"], indirect=True)
def test_validate_config_not_found(
        run_and_check_cli: RunAndCheckCLICallable,
        temp_config_paths: submanager.models.config.ConfigPaths,
        minimal: str,
        ) -> None:
    """Test that the generated config validates false."""
    run_and_check_cli(
        VALIDATE_COMMAND,
        *[OFFLINE_ONLY_ARG, minimal],
        config_paths=temp_config_paths,
        check_text="not found",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigNotFoundError,
        )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize(
    "temp_config_paths",
    CONFIG_EXTENSIONS_GOOD + CONFIG_EXTENSIONS_BAD,
    indirect=True,
    )
def test_validate_unknown_extension_empty_error(
        run_and_check_cli: RunAndCheckCLICallable,
        empty_config: submanager.models.config.ConfigPaths,
        minimal: str,
        ) -> None:
    """Test that validating a config file with an unknown extension errors."""
    extension = empty_config.static.suffix.lstrip(".")
    check_error: type[submanager.exceptions.SubManagerUserError]
    if extension == "json":
        check_text = "pars"
        check_error = submanager.exceptions.ConfigParsingError
    elif extension in CONFIG_EXTENSIONS_GOOD:
        check_text = "empty"
        check_error = submanager.exceptions.ConfigEmptyError
    else:
        check_text = "extension"
        check_error = submanager.exceptions.ConfigExtensionError
    run_and_check_cli(
        VALIDATE_COMMAND,
        *[OFFLINE_ONLY_ARG, minimal],
        config_paths=empty_config,
        check_text=check_text,
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=check_error,
        )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("temp_config_paths", ["json"], indirect=True)
def test_validate_config_list(
        run_and_check_cli: RunAndCheckCLICallable,
        list_config: submanager.models.config.ConfigPaths,
        minimal: str,
        ) -> None:
    """Test that the generated config validates false."""
    run_and_check_cli(
        VALIDATE_COMMAND,
        *[OFFLINE_ONLY_ARG, minimal],
        config_paths=list_config,
        check_text="structure",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigDataTypeError,
        )
