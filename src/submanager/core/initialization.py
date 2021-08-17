"""Setup and initialization code for the core routines."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
from typing import (
    Tuple,
)

# Third party imports
import praw.reddit

# Local imports
import submanager.config.dynamic
import submanager.config.static
import submanager.exceptions
import submanager.models.config
import submanager.utils.output
from submanager.constants import (
    USER_AGENT,
)
from submanager.types import (
    AccountsMap,
)

StaticDynamicTuple = Tuple[
    submanager.models.config.StaticConfig,
    submanager.models.config.DynamicConfig,
]


def setup_accounts(
    accounts_config: submanager.models.config.AccountsConfig,
    *,
    verbose: bool = False,
) -> AccountsMap:
    """Set up the PRAW Reddit objects for each account in the config."""
    vprint = submanager.utils.output.VerbosePrinter(verbose)

    # For each account, create and set up the Reddit object
    accounts = {}
    for account_key, account_kwargs in accounts_config.items():
        vprint(f"Setting up account {account_key!r}")
        try:
            reddit = praw.reddit.Reddit(
                user_agent=USER_AGENT,
                check_for_async=False,
                praw8_raise_exception_on_me=True,
                **account_kwargs.config,
            )
        except submanager.exceptions.PRAW_ALL_ERRORS as error:
            raise submanager.exceptions.AccountConfigError(
                account_key=account_key,
                message_post=error,
            ) from error
        reddit.validate_on_submit = True
        accounts[account_key] = reddit
    return AccountsMap(accounts)


def setup_config(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    verbose: bool = False,
) -> StaticDynamicTuple:
    """Load the config and set up the accounts mapping."""
    vprint = submanager.utils.output.VerbosePrinter(verbose)
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()

    # Load the configuration
    vprint(
        "Loading static configuration at path "
        f"{config_paths.static.as_posix()!r}",
    )
    static_config = submanager.config.static.load_static_config(
        config_paths.static,
    )
    vprint(
        "Loading dynamic configuration at path "
        f"{config_paths.dynamic.as_posix()!r}",
    )
    dynamic_config = submanager.config.dynamic.load_dynamic_config(
        static_config=static_config,
        config_path=config_paths.dynamic,
    )

    return static_config, dynamic_config
