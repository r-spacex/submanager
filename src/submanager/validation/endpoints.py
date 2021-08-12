"""Validate source and target sync endpoint objects."""

# Future imports
from __future__ import annotations

# Third party imports
import prawcore.exceptions

# Local imports
import submanager.endpoint.creation
import submanager.exceptions
import submanager.models.config
import submanager.utils.output
from submanager.types import (
    AccountsMap,
)


def validate_endpoint(
    config: submanager.models.config.EndpointTypeConfig,
    accounts: AccountsMap,
    *,
    check_editable: bool | None = None,
    raise_error: bool = True,
) -> bool:
    """Validate that the sync endpoint points to a valid Reddit object."""
    if check_editable is None:
        check_editable = "target" in config.uid
    reddit = accounts[config.context.account]

    details_urls = [
        "https://www.reddit.com/dev/api/oauth",
        "https://praw.readthedocs.io/en/stable/tutorials/refresh_token.html",
    ]
    endpoint_valid = False

    try:  # pylint: disable = too-many-try-statements
        # Create and validate each endpoint for read and write status
        endpoint = (
            submanager.endpoint.creation.create_sync_endpoint_from_config(
                config=config, reddit=reddit, validate=False
            )
        )
        endpoint_valid = endpoint.validate(raise_error=raise_error)
        if endpoint_valid and check_editable:
            endpoint_valid = bool(
                endpoint.check_is_editable(raise_error=raise_error)
            )
    except prawcore.exceptions.InsufficientScope as error:
        if not raise_error:
            return False
        urls_formatted = " or ".join([f"<{url}>" for url in details_urls])
        raise submanager.exceptions.InsufficientScopeError(
            config,
            message_pre=(
                f"Could not {'edit' if endpoint_valid else 'retrieve'} "
                f"{config.endpoint_type} due to the OAUTH scopes "
                f"{reddit.auth.scopes()!r} "
                f"of the refresh token for account {config.context.account!r} "
                "not including the scope required for this operation "
                f"(see {urls_formatted} for details)"
            ),
            message_post=error,
        ) from error

    return endpoint_valid


def get_all_endpoints(
    static_config: submanager.models.config.StaticConfig,
    *,
    include_disabled: bool = False,
) -> list[submanager.models.config.FullEndpointConfig]:
    """Get all sync endpoints defined in the current static config."""
    all_endpoints: list[submanager.models.config.FullEndpointConfig] = []
    # Get each sync pair source and target that is enabled
    if include_disabled or static_config.sync_manager.enabled:
        for sync_item in static_config.sync_manager.items.values():
            if include_disabled or sync_item.enabled:
                all_endpoints.append(sync_item.source)
                all_endpoints += list(sync_item.targets.values())
    # Get each thread endpoint that's enabled
    if include_disabled or static_config.thread_manager.enabled:
        for thread in static_config.thread_manager.items.values():
            if include_disabled or thread.enabled:
                all_endpoints.append(thread.source)
    # Pune the endpoints to just enabled unless told otherwise
    if not include_disabled:
        all_endpoints = [
            endpoint for endpoint in all_endpoints if endpoint.enabled
        ]
    return all_endpoints


def validate_endpoints(
    static_config: submanager.models.config.StaticConfig,
    accounts: AccountsMap,
    *,
    include_disabled: bool = False,
    raise_error: bool = True,
    verbose: bool = False,
) -> dict[str, bool]:
    """Validate all the endpoints defined in the config."""
    vprint = submanager.utils.output.VerbosePrinter(verbose)
    vprint("Extracting all endpoints from config")
    all_endpoints = get_all_endpoints(
        static_config=static_config, include_disabled=include_disabled
    )

    # Check if each endpoint is valid
    endpoints_valid = {}
    for endpoint in all_endpoints:
        vprint(f"Validating endpoint {endpoint.uid!r}")
        endpoint_valid = validate_endpoint(
            config=endpoint, accounts=accounts, raise_error=raise_error
        )
        endpoints_valid[endpoint.uid] = endpoint_valid

    return endpoints_valid
