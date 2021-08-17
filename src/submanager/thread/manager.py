"""Perform the tasks necessary to create a new thread and deprecate the old."""

# Future imports
from __future__ import (
    annotations,
)

# Local imports
import submanager.models.config
import submanager.thread.creation
import submanager.thread.sync
import submanager.thread.utils
from submanager.types import (
    AccountsMap,
)


def manage_thread(
    thread_config: submanager.models.config.ThreadItemConfig,
    dynamic_config: submanager.models.config.DynamicThreadItemConfig,
    accounts: AccountsMap,
    *,
    post_new_thread: bool | None = None,
    verbose: bool = True,
) -> None:
    """Manage the current thread, creating or updating it as necessary."""
    vprint = submanager.utils.output.VerbosePrinter(enable=verbose)
    if not thread_config.enabled:
        return

    # Determine if its time to post a new thread
    if post_new_thread is None:
        post_new_thread = submanager.thread.utils.should_post_new_thread(
            thread_config=thread_config,
            dynamic_config=dynamic_config,
            reddit=accounts[thread_config.context.account],
        )

    # If needed, post a new thread
    if post_new_thread:
        vprint(
            "Creating new thread for",
            thread_config.description,
            f"{thread_config.uid}",
        )
        submanager.thread.creation.handle_new_thread(
            thread_config,
            dynamic_config,
            accounts,
        )
    # Otherwise, sync the current thread
    else:
        submanager.thread.sync.sync_thread(
            thread_config=thread_config,
            dynamic_config=dynamic_config,
            accounts=accounts,
        )


def manage_threads(
    manager_config: submanager.models.config.ThreadManagerConfig,
    dynamic_config: submanager.models.config.DynamicThreadManagerConfig,
    accounts: AccountsMap,
) -> None:
    """Check and create/update all defined threads for a sub."""
    for thread_key, thread_config in manager_config.items.items():
        manage_thread(
            thread_config=thread_config,
            dynamic_config=dynamic_config.items[thread_key],
            accounts=accounts,
        )
