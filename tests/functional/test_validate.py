"""Test that the validate-config command correctly validates configuration."""

# Future imports
from __future__ import annotations


# Standard library imports
from typing import (
    Tuple,  # Not needed in Python 3.9
    Type,  # Not needed in Python 3.9
    )

# Third party imports
import pytest
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )


# Local imports
import submanager.enums
import submanager.exceptions
import submanager.models.config
from submanager.types import (
    ConfigDict,
    )
from tests.functional.conftest import (
    CONFIG_EXTENSIONS_BAD,
    CONFIG_EXTENSIONS_GOOD,
    CONFIG_PATHS_ALL,
    RunAndCheckCLICallable,
    )


# ---- Types ----

ExpectedTuple = Tuple[str, Type[submanager.exceptions.SubManagerUserError]]


# ---- Constants ----

VALIDATE_COMMAND: Final[str] = "validate-config"
OFFLINE_ONLY_ARG: Final[str] = "--offline-only"

MINIMAL_ARGS: Final[list[str]] = ["", "--minimal"]
INCLUDE_DISABLED_ARGS: Final[list[str]] = ["", "--include-disabled"]

VALIDATION_EXPECTED: Final[ExpectedTuple] = (
    "validat", submanager.exceptions.ConfigValidationError)
ACCOUNT_EXPECTED: Final[ExpectedTuple] = (
    "account", submanager.exceptions.AccountConfigError)
READONLY_EXPECTED: Final[ExpectedTuple] = (
    "read", submanager.exceptions.RedditReadOnlyError)
BAD_VALIDATE_PARAMS: Final[list[tuple[ConfigDict, ExpectedTuple]]] = [
    ({"non_existant_key": "Non-Existant Value"}, VALIDATION_EXPECTED),
    ({"context_default": {"account": 42}}, VALIDATION_EXPECTED),
    ({"context_default": {"account": "missing_account"}}, VALIDATION_EXPECTED),
    ({"context_default": {"subreddit": 42}}, VALIDATION_EXPECTED),
    ({"context_default": {"subreddit": None}}, VALIDATION_EXPECTED),
    ({"accounts": {"muskbot": {"client_id": None}}}, ACCOUNT_EXPECTED),
    ({"accounts": {"muskrat": {"site_name": "MISSINGNO"}}}, ACCOUNT_EXPECTED),
    ({"accounts": {"muskbot": {"refresh_token": None}}}, READONLY_EXPECTED),
    ({"accounts": {"muskrat": {"password": None}}}, READONLY_EXPECTED),
    ]
BAD_VALIDATE_IDS = [
    "nonexistant_value",
    "account_int",
    "account_nonmatch",
    "subreddit_int",
    "subreddit_missing",
    "client_id_missing",
    "site_name_nomatch",
    "token_missing",
    "password_missing",
    ]


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
def test_config_not_found(
        run_and_check_cli: RunAndCheckCLICallable,
        temp_config_paths: submanager.models.config.ConfigPaths,
        minimal: str,
        ) -> None:
    """Test that the config not being found validates false."""
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
def test_config_empty_error(
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
def test_config_list_error(
        run_and_check_cli: RunAndCheckCLICallable,
        list_config: submanager.models.config.ConfigPaths,
        minimal: str,
        ) -> None:
    """Test that a config file with the wrong data structure fails validate."""
    run_and_check_cli(
        VALIDATE_COMMAND,
        *[OFFLINE_ONLY_ARG, minimal],
        config_paths=list_config,
        check_text="structure",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigDataTypeError,
        )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("include_disabled", INCLUDE_DISABLED_ARGS)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ALL, indirect=True)
def test_valid_offline(
        run_and_check_cli: RunAndCheckCLICallable,
        file_config: submanager.models.config.ConfigPaths,
        minimal: str,
        include_disabled: str,
        ) -> None:
    """Test that the test configs validate true in offline mode."""
    run_and_check_cli(
        VALIDATE_COMMAND,
        *[OFFLINE_ONLY_ARG, minimal, include_disabled],
        config_paths=file_config,
        check_text="succe",
        )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ALL, indirect=True)
def test_parsing_error(
        run_and_check_cli: RunAndCheckCLICallable,
        file_config: submanager.models.config.ConfigPaths,
        minimal: str,
        ) -> None:
    """Test that config files with an invalid file format validate false."""
    with open(file_config.static, mode="r", encoding="utf-8") as config_file:
        config_file_text = config_file.read()
    config_file_text = config_file_text.replace('"', "", 1)
    with open(file_config.static, mode="w",
              encoding="utf-8", newline="\n") as config_file:
        config_file.write(config_file_text)

    run_and_check_cli(
        VALIDATE_COMMAND,
        *[OFFLINE_ONLY_ARG, minimal],
        config_paths=file_config,
        check_text="pars",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigParsingError,
        )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ALL, indirect=True)
@pytest.mark.parametrize(
    "modified_config, check_vars",
    BAD_VALIDATE_PARAMS,
    ids=BAD_VALIDATE_IDS,
    indirect=["modified_config"],
    )
def test_value_error(
        run_and_check_cli: RunAndCheckCLICallable,
        modified_config: submanager.models.config.ConfigPaths,
        check_vars: ExpectedTuple,
        minimal: str,
        ) -> None:
    """Test that config files with a bad value validate false."""
    check_text, check_error = check_vars
    if minimal and check_error == submanager.exceptions.RedditReadOnlyError:
        run_and_check_cli(
            VALIDATE_COMMAND,
            *[OFFLINE_ONLY_ARG, minimal],
            config_paths=modified_config,
            check_text="succe",
            )
    else:
        run_and_check_cli(
            VALIDATE_COMMAND,
            *[OFFLINE_ONLY_ARG, minimal],
            config_paths=modified_config,
            check_text=check_text,
            check_code=submanager.enums.ExitCode.ERROR_USER,
            check_error=check_error,
            )
