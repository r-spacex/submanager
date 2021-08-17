"""Sync between a source endpoint and one or more targets."""

# Future imports
from __future__ import (
    annotations,
)

# Local imports
import submanager.endpoint.creation
import submanager.models.config
import submanager.sync.processing
from submanager.types import (
    AccountsMap,
)


def sync_one(
    sync_item: submanager.models.config.SyncItemConfig,
    dynamic_config: submanager.models.config.DynamicSyncItemConfig,
    accounts: AccountsMap,
) -> None:
    """Sync one specific pair of sources and targets."""
    if not (sync_item.enabled and sync_item.source.enabled):
        return

    # Create source sync endpoint
    source_obj = submanager.endpoint.creation.create_sync_endpoint_from_config(
        config=sync_item.source,
        reddit=accounts[sync_item.source.context.account],
    )
    source_content = submanager.sync.processing.process_source_endpoint(
        sync_item.source,
        source_obj,
        dynamic_config,
    )
    if source_content is False:
        return

    # Create target endpoints, process data and sync
    for target_config in sync_item.targets.values():
        if not target_config.enabled:
            continue

        target_obj = (
            submanager.endpoint.creation.create_sync_endpoint_from_config(
                config=target_config,
                reddit=accounts[target_config.context.account],
            )
        )
        target_content = submanager.sync.processing.process_target_endpoint(
            target_config=target_config,
            target_obj=target_obj,
            source_content=source_content,
            menu_config=sync_item.source.menu_config,
        )
        if target_content is False:
            continue

        target_obj.edit(
            target_content,
            reason=(
                f"Auto-sync {sync_item.description or sync_item.uid} "
                f"from {target_obj.config.endpoint_name}"
            ),
        )


def sync_all(
    manager_config: submanager.models.config.SyncManagerConfig,
    dynamic_config: submanager.models.config.DynamicSyncManagerConfig,
    accounts: AccountsMap,
) -> None:
    """Sync all pairs of sources/targets (pages,threads, sections) on a sub."""
    for sync_item_id, sync_item in manager_config.items.items():
        sync_one(
            sync_item=sync_item,
            dynamic_config=dynamic_config.items[sync_item_id],
            accounts=accounts,
        )
