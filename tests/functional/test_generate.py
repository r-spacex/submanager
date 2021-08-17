"""Test that the generate-config command works as expected in the CLI."""

# Future imports
from __future__ import (
    annotations,
)

# Third party imports
import pytest
from typing_extensions import (
    Final,
)

# Local imports
import submanager.core.initialization
import submanager.enums
import submanager.exceptions
import submanager.models.config
import submanager.validation.validate
from tests.functional.conftest import (
    CONFIG_EXTENSIONS_BAD,
    DEBUG_ARGS,
    RunAndCheckCLICallable,
)

# ---- Constants ----

GENERATE_COMMAND: Final[str] = "generate-config"
FORCE_ARGS: Final[list[str]] = ["", "--force"]
EXIST_OK_ARGS: Final[list[str]] = ["", "--exist-ok"]


# ---- Tests ----


@pytest.mark.parametrize("temp_config_dir", ["", "missing_dir"], indirect=True)
@pytest.mark.parametrize("exist_ok", EXIST_OK_ARGS)
@pytest.mark.parametrize("force", FORCE_ARGS)
def test_config_doesnt_exist(
    run_and_check_cli: RunAndCheckCLICallable,
    temp_config_paths: submanager.models.config.ConfigPaths,
    force: str,
    exist_ok: str,
) -> None:
    """Test that the config file is generated when one doesn't exist."""
    run_and_check_cli(
        cli_args=[GENERATE_COMMAND, force, exist_ok],
        config_paths=temp_config_paths,
        check_text="generat",
    )

    assert temp_config_paths.static.exists()
    submanager.core.initialization.setup_config(
        temp_config_paths,
        verbose=True,
    )


@pytest.mark.parametrize("exist_ok", EXIST_OK_ARGS)
@pytest.mark.parametrize("force", FORCE_ARGS)
def test_config_exists(
    run_and_check_cli: RunAndCheckCLICallable,
    empty_config: submanager.models.config.ConfigPaths,
    force: str,
    exist_ok: str,
) -> None:
    """Test config file generation when one does exist."""
    run_and_check_cli(
        cli_args=[GENERATE_COMMAND, force, exist_ok],
        config_paths=empty_config,
        check_text="overwrit" if force else "exist",
        check_exits=not bool(force or exist_ok),
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigExistsError,
    )

    if force:
        assert empty_config.static.exists()
        submanager.core.initialization.setup_config(empty_config, verbose=True)


@pytest.mark.parametrize(
    "temp_config_paths",
    CONFIG_EXTENSIONS_BAD,
    indirect=True,
)
def test_unknown_extension_error(
    run_and_check_cli: RunAndCheckCLICallable,
    temp_config_paths: submanager.models.config.ConfigPaths,
) -> None:
    """Test that generating a config file with an unknown extension errors."""
    run_and_check_cli(
        cli_args=[GENERATE_COMMAND],
        config_paths=temp_config_paths,
        check_text="extension",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigExtensionError,
    )


def test_generated_validates_false(
    run_and_check_cli: RunAndCheckCLICallable,
    temp_config_paths: submanager.models.config.ConfigPaths,
) -> None:
    """Test that the generated config file validates successfully."""
    run_and_check_cli(
        cli_args=[GENERATE_COMMAND],
        config_paths=temp_config_paths,
        check_text="generat",
    )

    with pytest.raises(submanager.exceptions.ConfigDefaultError):
        submanager.validation.validate.validate_config(
            config_paths=temp_config_paths,
            offline_only=True,
            raise_error=True,
            verbose=True,
        )

    static_config, __ = submanager.core.initialization.setup_config(
        temp_config_paths,
        verbose=True,
    )
    with pytest.raises(submanager.exceptions.AccountConfigError):
        submanager.core.initialization.setup_accounts(
            static_config.accounts,
            verbose=True,
        )


@pytest.mark.parametrize("debug", DEBUG_ARGS)
def test_debug_error(
    run_and_check_cli: RunAndCheckCLICallable,
    empty_config: submanager.models.config.ConfigPaths,
    debug: str,
) -> None:
    """Test that --debug allows the error to bubble up and dump traceback."""
    check_text = "exist"
    check_error = submanager.exceptions.ConfigExistsError
    try:
        run_and_check_cli(
            cli_args=[debug, GENERATE_COMMAND],
            config_paths=empty_config,
            check_text=check_text,
            check_code=submanager.enums.ExitCode.ERROR_USER,
            check_error=check_error,
        )
    except submanager.exceptions.SubManagerUserError as error:
        assert isinstance(error, check_error)
        assert check_text in str(error)
