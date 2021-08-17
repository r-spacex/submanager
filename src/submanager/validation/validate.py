"""Perform validation on the configuration and environment."""

# Future imports
from __future__ import (
    annotations,
)

# Local imports
import submanager.core.initialization
import submanager.exceptions
import submanager.models.config
import submanager.utils.output
import submanager.validation.accounts
import submanager.validation.connection
import submanager.validation.endpoints
import submanager.validation.offline


def validate_config(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    offline_only: bool = False,
    minimal: bool = False,
    include_disabled: bool = False,
    raise_error: bool = True,
    verbose: bool = False,
) -> bool:
    """Check if the config is valid."""
    vprint = submanager.utils.output.FancyPrinter(enable=verbose)
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()

    try:  # pylint: disable = too-many-try-statements
        vprint("Loading config", level=1)
        static_config, __ = submanager.core.initialization.setup_config(
            config_paths=config_paths,
            verbose=verbose,
        )

        if not minimal:
            vprint("Checking config offline", level=1)
            submanager.validation.offline.validate_offline_config(
                static_config=static_config,
                config_paths=config_paths,
                raise_error=True,
                verbose=verbose,
            )
        vprint("Loading accounts", level=1)
        accounts = submanager.core.initialization.setup_accounts(
            static_config.accounts,
            verbose=verbose,
        )

        if not minimal:
            if not offline_only:
                vprint("Checking Reddit connectivity", level=1)
                submanager.validation.connection.check_reddit_connectivity(
                    raise_error=True,
                )

            vprint("Checking accounts", level=1)
            submanager.validation.accounts.validate_accounts(
                accounts=accounts,
                offline_only=offline_only,
                check_readonly=static_config.check_readonly,
                raise_error=True,
                verbose=verbose,
            )

            if not offline_only:
                vprint("Checking endpoints", level=1)
                submanager.validation.endpoints.validate_endpoints(
                    static_config=static_config,
                    accounts=accounts,
                    include_disabled=include_disabled,
                    raise_error=True,
                    verbose=verbose,
                )

    except submanager.exceptions.SubManagerUserError:
        if not raise_error:
            return False
        raise

    return True
