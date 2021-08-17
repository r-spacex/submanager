"""Example configuration setup for the package."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
from types import (
    MappingProxyType,
)
from typing import (
    Any,
    Mapping,
)

# Third party imports
from typing_extensions import (
    Final,
)

# Local imports
import submanager.models.base
import submanager.models.config

# ---- General constants ----

# Fields to not output in the generated config, as they are too verbose
ENDPOINT_EXCLUDE_FIELDS: Final[frozenset[str]] = frozenset(("context", "uid"))
EXAMPLE_EXCLUDE_FIELDS: Final[Mapping[str | int, Any]] = MappingProxyType(
    {
        "sync_manager": {
            "items": {
                "EXAMPLE_SYNC_ITEM": {
                    "source": ENDPOINT_EXCLUDE_FIELDS,
                    "target": ENDPOINT_EXCLUDE_FIELDS,
                    "uid": ...,
                },
            },
        },
        "thread_manager": {
            "items": {
                "EXAMPLE_THREAD": {
                    "context": ...,
                    "source": ENDPOINT_EXCLUDE_FIELDS,
                    "target_context": ...,
                    "uid": ...,
                },
            },
        },
    },
)


# ---- Example elements ----

EXAMPLE_ACCOUNT_NAME: Final[str] = "EXAMPLE_USER"

EXAMPLE_ACCOUNT_CONFIG: Final = submanager.models.config.AccountConfig(
    config={"site_name": "EXAMPLE_SITE_NAME"},
)

EXAMPLE_ACCOUNTS: Final = submanager.models.config.AccountsConfig(
    {
        EXAMPLE_ACCOUNT_NAME: EXAMPLE_ACCOUNT_CONFIG,
    },
)

EXAMPLE_CONTEXT: Final = submanager.models.base.ContextConfig(
    account="EXAMPLE_USER",
    subreddit="EXAMPLESUBREDDIT",
)

EXAMPLE_SOURCE: Final = submanager.models.config.FullEndpointConfig(
    context=EXAMPLE_CONTEXT,
    description="Example sync source",
    endpoint_name="EXAMPLE_SOURCE_NAME",
    replace_patterns={"https://old.reddit.com": "https://www.reddit.com"},
    uid="EXAMPLE_SOURCE",
)

EXAMPLE_TARGET: Final = submanager.models.config.FullEndpointConfig(
    context=EXAMPLE_CONTEXT,
    description="Example sync target",
    endpoint_name="EXAMPLE_TARGET_NAME",
    uid="EXAMPLE_TARGET",
)

EXAMPLE_SYNC_ITEM: Final = submanager.models.config.SyncItemConfig(
    description="Example sync item",
    enabled=False,
    source=EXAMPLE_SOURCE,
    targets={"EXAMPLE_TARGET": EXAMPLE_TARGET},
    uid="EXAMPLE_SYNC_ITEM",
)


EXAMPLE_THREAD: Final = submanager.models.config.ThreadItemConfig(
    context=EXAMPLE_CONTEXT,
    description="Example managed thread",
    enabled=False,
    source=EXAMPLE_SOURCE,
    target_context=EXAMPLE_CONTEXT,
    uid="EXAMPLE_THREAD",
)


EXAMPLE_STATIC_CONFIG: Final = submanager.models.config.StaticConfig(
    accounts=EXAMPLE_ACCOUNTS,
    context_default=EXAMPLE_CONTEXT,
    sync_manager=submanager.models.config.SyncManagerConfig(
        items={"EXAMPLE_SYNC_ITEM": EXAMPLE_SYNC_ITEM},
    ),
    thread_manager=submanager.models.config.ThreadManagerConfig(
        items={"EXAMPLE_THREAD": EXAMPLE_THREAD},
    ),
)
