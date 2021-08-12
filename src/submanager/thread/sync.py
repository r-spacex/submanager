"""Sync automatically-managed threads from a source endpoint."""

# Future imports
from __future__ import (
    annotations,
)

# Local imports
import submanager.enums
import submanager.exceptions
import submanager.models.config
import submanager.sync.manager
import submanager.thread.utils
from submanager.types import (
    AccountsMap,
)


def sync_thread(
    thread_config: submanager.models.config.ThreadItemConfig,
    dynamic_config: submanager.models.config.DynamicThreadItemConfig,
    accounts: AccountsMap,
) -> None:
    """Sync a managed thread from its source."""
    if not dynamic_config.thread_id:
        raise submanager.exceptions.SubManagerValueError(
            "Thread ID for must be specified for thread sync to work "
            f"for thread {thread_config!r}",
            message_post=f"Dynamic Config: {dynamic_config!r}",
        )

    thread_target = submanager.models.config.FullEndpointConfig(
        context=thread_config.target_context,
        description=f"{thread_config.description or thread_config.uid} Thread",
        endpoint_name=dynamic_config.thread_id,
        endpoint_type=submanager.enums.EndpointType.THREAD,
        pattern=submanager.thread.utils.THREAD_PATTERN,
        pattern_end=thread_config.source.pattern_end,
        pattern_start=thread_config.source.pattern_start,
        uid=thread_config.uid + ".target",
    )
    sync_item = submanager.models.config.SyncItemConfig(
        description=thread_config.description,
        source=thread_config.source,
        targets={"managed_thread": thread_target},
        uid=thread_config.uid + ".sync_item",
    )
    submanager.sync.manager.sync_one(
        sync_item=sync_item,
        dynamic_config=dynamic_config,
        accounts=accounts,
    )
