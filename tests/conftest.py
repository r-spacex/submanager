"""Common top-level test fixtures."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import configparser
import os
from pathlib import (
    Path,
)
from typing import (
    Collection,
    Mapping,
)

# Third party imports
import platformdirs
import pytest
from _pytest.config import (  # noqa: WPS436
    Config,
)
from _pytest.config.argparsing import (  # noqa: WPS436
    Parser,
)
from typing_extensions import (
    Final,
)

# ---- Constants ----

PACKAGE_NAME: Final[str] = "submanager"

LINE_LENGTH: Final[int] = 70

RUN_ONLINE_OPTION: Final[str] = "--run-online"

PRAW_INI_FILENAME: Final[str] = "praw.ini"
PRAW_INI_PATH_LOCAL: Final[Path] = Path() / PRAW_INI_FILENAME
PRAW_ENV_VARS_REQUIRED: Final[set[str]] = {
    "praw_client_id",
    "praw_client_secret",
}
PRAW_ENV_VARS_REFRESH: Final[set[str]] = {"praw_refresh_token"}
PRAW_ENV_VARS_PASSWORD: Final[set[str]] = {"praw_username", "praw_password"}
PRAW_ENV_VARS_ALL: Final[set[str]] = (
    PRAW_ENV_VARS_REQUIRED | PRAW_ENV_VARS_REFRESH | PRAW_ENV_VARS_PASSWORD
)
TEST_SITE_NAME: Final[str] = "submanager_testbot"

DUMMY_ACCOUNT_CONFIG: Final[dict[str, str]] = {
    "client_id": "abcdefgABCDEFG",
    "client_secret": "abcdefghijklmnopqrstuvwxyzABCD",
    "refresh_token": "123456789100-abcdefghijklmnopqrstuvwxyzABCD",
}


# ---- Helpers ----


def _get_praw_ini_has_site_name(site_name: str) -> bool | None:
    """Determine whether the default praw.ini file contains the site."""
    praw_config = configparser.ConfigParser()
    user_config_path = platformdirs.user_config_path(roaming=True)
    praw_ini_path = user_config_path / PRAW_INI_FILENAME
    if not praw_ini_path.exists():
        return None
    try:
        praw_config.read(praw_ini_path)
    except configparser.Error:
        return None
    return praw_config.has_section(site_name)


def _check_env_var_set(env_var: str) -> bool:
    """Check if the environment variable is set to a non-whitespace value."""
    env_var_value = os.getenv(env_var)
    return bool(env_var_value and env_var_value.strip())


def _get_missing_env_vars(required_env_vars: Collection[str]) -> set[str]:
    """Get the current environment variables missing from a given set."""
    missing_env_vars = {
        required_env_var
        for required_env_var in required_env_vars
        if not _check_env_var_set(required_env_var)
    }
    return missing_env_vars


def _get_missing_praw_env_vars() -> set[str]:
    """Get the required PRAW environment variables that are not present."""
    missing_env_vars: set[str] = set()
    missing_env_vars |= _get_missing_env_vars(PRAW_ENV_VARS_REQUIRED)
    missing_refresh = _get_missing_env_vars(PRAW_ENV_VARS_REFRESH)
    missing_password = _get_missing_env_vars(PRAW_ENV_VARS_PASSWORD)
    if not missing_refresh or not missing_password:
        return missing_env_vars
    if missing_password != PRAW_ENV_VARS_PASSWORD:
        missing_env_vars |= missing_password
        return missing_env_vars
    missing_env_vars |= missing_refresh
    return missing_env_vars


def _get_val_id_from_collection(
    val: Collection[object],  # noqa: WPS110
) -> str | object:
    """Extract a suitible test ID string from a collection, if possible."""
    if isinstance(val, Mapping):
        # static analysis: ignore[undefined_attribute]
        val_iter = iter(val.values())
    else:
        val_iter = iter(val)
    if len(val) == 1:
        val_id: object = next(val_iter)
        return val_id
    if all(isinstance(val_item, str) for val_item in val):
        # static analysis: ignore[incompatible_argument]
        return " ".join(val)  # type: ignore[arg-type]

    return val


def _get_val_id(val: object) -> str | object:  # noqa: WPS110
    """Get the ID string from an arbitrary test param object, if possible."""
    val_name: object = getattr(val, "name", None)
    if isinstance(val, Path):
        return val.stem
    # static analysis: ignore[non_boolean_in_boolean_context]
    if val_name and isinstance(val_name, str):
        return val_name
    if isinstance(val, Collection):
        # static analysis: ignore[incompatible_argument]
        return _get_val_id_from_collection(val)

    return val


# ---- Hooks ----


def pytest_addoption(parser: Parser) -> None:
    """Add an option to run online tests to the pytest argument parser."""
    parser.addoption(
        RUN_ONLINE_OPTION,
        action="store_true",
        default=False,
        help="Run tests that require interacting with live Reddit",
    )


def pytest_configure(config: Config) -> None:
    """Add a temporary local PRAW.ini with the test bot site if not found."""
    run_online = config.getoption(RUN_ONLINE_OPTION)
    has_test_site_name = _get_praw_ini_has_site_name(TEST_SITE_NAME)
    if run_online and has_test_site_name:
        return

    if run_online:
        missing_env_vars = _get_missing_praw_env_vars()
        if missing_env_vars:
            error_highlight = "*" * (LINE_LENGTH // 2)
            error_divider = f"{error_highlight} WARNING {error_highlight}"
            error_message = (
                f"PRAW site {TEST_SITE_NAME!r} missing in praw.ini "
                f"and environment variable(s) not found:\n{missing_env_vars}\n"
                "Online tests will fail due to lacking Reddit authentication"
            )
            error_message_full = "\n".join(
                ["", error_divider, error_message, error_divider, ""],
            )
            print(error_message_full)  # noqa: WPS421

    praw_config = configparser.ConfigParser()
    praw_config[TEST_SITE_NAME] = DUMMY_ACCOUNT_CONFIG
    with open(
        PRAW_INI_PATH_LOCAL,
        mode="w",
        encoding="utf-8",
    ) as praw_ini_file_offline:
        praw_config.write(praw_ini_file_offline)


def pytest_unconfigure(
    config: Config,  # pylint: disable = unused-argument
) -> None:
    """Remove the temporary PRAW.ini in the working directory."""
    praw_ini_path = PRAW_INI_PATH_LOCAL
    if praw_ini_path.exists():
        praw_ini_path.unlink()


def pytest_collection_modifyitems(
    config: Config,
    items: list[pytest.Item],
) -> None:
    """Ensure that online tests are skipped unless run online is passed."""
    if not config.getoption(RUN_ONLINE_OPTION):
        skip_online = pytest.mark.skip(reason="Needs --run-online")
        for item in items:
            if "online" in item.keywords:
                item.add_marker(skip_online)


def pytest_make_parametrize_id(val: object) -> str | None:  # noqa: WPS110
    """Intelligently generate parameter IDs; hook for pytest."""
    val_id: object
    if isinstance(val, (str, bytes)):
        val_id = val
    else:
        val_id = _get_val_id(val)

    if isinstance(val_id, bytes):
        return val_id.decode()
    if isinstance(val_id, str):
        return val_id.strip().strip("-").replace("-", "")
    if val_id is None or isinstance(val_id, (int, float, complex, bool)):
        return str(val_id)

    return None
