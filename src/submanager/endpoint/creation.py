"""Registration and generation of sync endpoints."""

# Future imports
from __future__ import annotations

# Standard library imports
from typing import (
    Mapping,  # Import from collections.abc in Python 3.9
    )

# Third party imports
import praw.reddit
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    Type,  # Not needed in Python 3.9
    )

# Local imports
import submanager.endpoint.base
import submanager.endpoint.endpoints
import submanager.enums
import submanager.models.config


EndpointClass = Type[submanager.endpoint.base.SyncEndpoint]

SYNC_ENDPOINT_TYPES: Final[Mapping[
        submanager.enums.EndpointType, EndpointClass]] = {
    submanager.enums.EndpointType.MENU: (
        submanager.endpoint.endpoints.MenuSyncEndpoint),
    submanager.enums.EndpointType.THREAD: (
        submanager.endpoint.endpoints.ThreadSyncEndpoint),
    submanager.enums.EndpointType.WIDGET: (
        submanager.endpoint.endpoints.SidebarSyncEndpoint),
    submanager.enums.EndpointType.WIKI_PAGE: (
        submanager.endpoint.endpoints.WikiSyncEndpoint),
    }


def create_sync_endpoint_from_config(
        config: submanager.models.config.EndpointTypeConfig,
        reddit: praw.reddit.Reddit,
        *,
        validate: bool = False,
        raise_error: bool = True,
        ) -> submanager.endpoint.base.SyncEndpoint:
    """Create a new sync endpoint given a particular config and Reddit obj."""
    sync_endpoint = SYNC_ENDPOINT_TYPES[config.endpoint_type](
        config=config,
        reddit=reddit,
        validate=validate,
        raise_error=raise_error,
        )
    return sync_endpoint
