"""Validate the configuration without making network requests."""

# Future imports
from __future__ import (
    annotations,
)

# Local imports
import submanager.exceptions
import submanager.models.config
import submanager.models.example
import submanager.utils.output


def validate_offline_config(
    static_config: submanager.models.config.StaticConfig,
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    error_default: bool = True,
    raise_error: bool = True,
    verbose: bool = False,
) -> bool:
    """Validate config locally without connecting to Reddit."""
    vprint = submanager.utils.output.VerbosePrinter(verbose)
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()

    # If default config was generated and is unmodified, raise an error
    if error_default:
        vprint("Checking that config has been set up")
        if static_config.accounts == (
            submanager.models.example.EXAMPLE_ACCOUNTS
        ):
            if not raise_error:
                return False
            raise submanager.exceptions.ConfigDefaultError(config_paths.static)

    return True
