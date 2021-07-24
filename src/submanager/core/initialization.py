"""Setup and initialization code for the core routines."""

# Future imports
from __future__ import annotations

# Standard library imports
import copy
from pathlib import Path

# Third party imports
import praw.reddit
import praw.util.token_manager

# Local imports
import submanager.config.dynamic
import submanager.config.static
import submanager.exceptions
import submanager.models.config
import submanager.utils.output
from submanager.constants import (
    CONFIG_PATH_REFRESH,
    USER_AGENT,
)
from submanager.types import (
    AccountsConfig,
    AccountsConfigProcessed,
    AccountsMap,
    PathLikeStr,
    )


def handle_refresh_tokens(
        accounts_config: AccountsConfig,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        ) -> AccountsConfigProcessed:
    """Set up each account with the appropriate refresh tokens."""
    config_path_refresh = Path(config_path_refresh)
    accounts_config_processed: AccountsConfigProcessed = (
        accounts_config)  # type: ignore[assignment]
    accounts_config_processed = copy.deepcopy(accounts_config_processed)

    # For each account, get and handle the refresh token
    for account_key, account_kwargs in accounts_config.items():
        refresh_token = account_kwargs.get("refresh_token", None)
        if refresh_token:
            del accounts_config_processed[account_key]["refresh_token"]
            # Initialize refresh token file
            token_path: Path = config_path_refresh.with_name(
                config_path_refresh.name.format(key=account_key))
            token_path.parent.mkdir(parents=True, exist_ok=True)
            if not token_path.exists():
                with open(token_path, "w",
                          encoding="utf-8", newline="\n") as token_file:
                    token_file.write(refresh_token)

            # Set up refresh token manager
            token_manager = praw.util.token_manager.FileTokenManager(
                token_path)  # type: ignore[no-untyped-call]
            accounts_config_processed[account_key]["token_manager"] = (
                token_manager)

    return accounts_config_processed


def setup_accounts(
        accounts_config: AccountsConfig,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        *,
        verbose: bool = False,
        ) -> AccountsMap:
    """Set up the PRAW Reddit objects for each account in the config."""
    vprint = submanager.utils.output.VerbosePrinter(verbose)

    vprint("Processing refresh tokens at path "
           f"{Path(config_path_refresh).as_posix()!r}")
    accounts_config_processed = handle_refresh_tokens(
        accounts_config, config_path_refresh=config_path_refresh)

    # For each account, create and set up the Reddit object
    accounts = {}
    for account_key, account_kwargs in accounts_config_processed.items():
        vprint(f"Setting up account {account_key!r}")
        try:
            reddit = praw.reddit.Reddit(
                user_agent=USER_AGENT,
                check_for_async=False,
                praw8_raise_exception_on_me=True,
                **account_kwargs,
                )
        except submanager.exceptions.PRAW_ALL_ERRORS as error:
            raise submanager.exceptions.AccountConfigError(
                account_key=account_key, message_post=error) from error
        reddit.validate_on_submit = True
        accounts[account_key] = reddit
    return accounts


def setup_config(
        config_paths: submanager.models.config.ConfigPaths | None = None,
        *,
        verbose: bool = False,
        ) -> tuple[submanager.models.config.StaticConfig,
                   submanager.models.config.DynamicConfig]:
    """Load the config and set up the accounts mapping."""
    vprint = submanager.utils.output.VerbosePrinter(verbose)
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()

    # Load the configuration
    vprint("Loading static configuration at path "
           f"{config_paths.static.as_posix()!r}")
    static_config = submanager.config.static.load_static_config(
        config_paths.static)
    vprint("Loading dynamic configuration at path "
           f"{config_paths.dynamic.as_posix()!r}")
    dynamic_config = submanager.config.dynamic.load_dynamic_config(
        static_config=static_config, config_path=config_paths.dynamic)

    return static_config, dynamic_config
