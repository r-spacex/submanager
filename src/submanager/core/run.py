"""Start the mainloop and run the bot."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import time
from typing import (
    Collection,
)

# Local imports
import submanager.config.dynamic
import submanager.config.utils
import submanager.core.initialization
import submanager.exceptions
import submanager.models.config
import submanager.sync.manager
import submanager.thread.manager
import submanager.validation.validate
from submanager.constants import (
    CONFIG_PATH_DYNAMIC,
)
from submanager.types import (
    AccountsMap,
    PathLikeStr,
)


def run_initial_setup(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    skip_validate: bool = False,
    resync_all: bool = False,
) -> tuple[submanager.models.config.StaticConfig, AccountsMap]:
    """Run initial run-time setup for each time the application is started."""
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()
    if not skip_validate:
        submanager.validation.validate.validate_config(
            config_paths=config_paths,
            offline_only=False,
            raise_error=True,
            verbose=True,
        )

    (
        static_config,
        dynamic_config,
    ) = submanager.core.initialization.setup_config(config_paths=config_paths)
    accounts = submanager.core.initialization.setup_accounts(
        static_config.accounts
    )

    # Reset the source timestamps so all items get resynced
    if resync_all:
        dynamic_items: list[
            submanager.models.config.DynamicSyncItemConfig
        ] = list(dynamic_config.sync_manager.items.values()) + list(
            dynamic_config.thread_manager.items.values()
        )
        for item in dynamic_items:
            item.source_timestamp = 0
        submanager.config.utils.write_config(
            dynamic_config, config_path=config_paths.dynamic
        )

    return static_config, accounts


def run_cycle_threads(
    thread_keys: Collection[str],
    config_paths: submanager.models.config.ConfigPaths | None = None,
) -> None:
    """Post new threads for one or more existing managed threads."""
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()
    thread_keys = set(thread_keys)

    static_config, accounts = run_initial_setup(
        config_paths, skip_validate=True, resync_all=False
    )
    managed_threads = static_config.thread_manager.items

    keys_notfound = thread_keys - managed_threads.keys()
    if keys_notfound:
        raise submanager.exceptions.SubManagerUserError(
            f"Thread keys {keys_notfound!r} not found in valid keys "
            f"{set(managed_threads.keys())!r}"
        )

    threads_tocycle = {
        thread_key: managed_threads[thread_key] for thread_key in thread_keys
    }
    with submanager.config.dynamic.LockedandLoadedDynamicConfig(
        static_config=static_config,
        config_path=config_paths.dynamic,
        verbose=True,
    ) as dynamic_config:
        for thread_key, thread_config in threads_tocycle.items():
            submanager.thread.manager.manage_thread(
                thread_config=thread_config,
                dynamic_config=dynamic_config.thread_manager.items[thread_key],
                accounts=accounts,
                post_new_thread=True,
            )
        submanager.config.utils.write_config(
            dynamic_config, config_path=config_paths.dynamic
        )


def run_manage_once(
    static_config: submanager.models.config.StaticConfig,
    accounts: AccountsMap,
    config_path_dynamic: PathLikeStr = CONFIG_PATH_DYNAMIC,
) -> None:
    """Run the manage loop once, without validation checks."""
    print("Running Sub Manager")
    # Lock and load dynamic config and set up session
    with submanager.config.dynamic.LockedandLoadedDynamicConfig(
        static_config=static_config,
        config_path=config_path_dynamic,
        verbose=True,
    ) as dynamic_config:
        dynamic_config_active = dynamic_config.copy(deep=True)

        # Run the core manager tasks
        if static_config.sync_manager.enabled:
            submanager.sync.manager.sync_all(
                static_config.sync_manager,
                dynamic_config_active.sync_manager,
                accounts,
            )
        if static_config.thread_manager.enabled:
            submanager.thread.manager.manage_threads(
                static_config.thread_manager,
                dynamic_config_active.thread_manager,
                accounts,
            )

        # Write out the dynamic config if it changed
        if dynamic_config_active != dynamic_config:
            submanager.config.utils.write_config(
                dynamic_config_active, config_path=config_path_dynamic
            )
    print("Sub Manager run complete")


def run_manage(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    skip_validate: bool = False,
    resync_all: bool = False,
) -> None:
    """Load the config file and run the thread manager."""
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()
    static_config, accounts = run_initial_setup(
        config_paths, skip_validate=skip_validate, resync_all=resync_all
    )
    run_manage_once(
        static_config=static_config,
        accounts=accounts,
        config_path_dynamic=config_paths.dynamic,
    )


def start_manage(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    skip_validate: bool = False,
    repeat_interval_s: float | None = None,
    repeat_max_n: int | None = None,
) -> None:
    """Run the mainloop of Sub Manager, performing each task in sequance."""
    # Load config and set up session
    print("Starting Sub Manager")
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()
    static_config, accounts = run_initial_setup(
        config_paths, skip_validate=skip_validate, resync_all=True
    )
    if repeat_interval_s is None:
        repeat_interval_s = static_config.repeat_interval_s

    while True:
        # Run the bot
        run_manage_once(
            static_config=static_config,
            accounts=accounts,
            config_path_dynamic=config_paths.dynamic,
        )
        if repeat_max_n is not None:
            repeat_max_n -= 1
            if repeat_max_n <= 0:
                break

        # Wait until the desired time of the next cycle
        time_left_s = repeat_interval_s
        try:  # pylint: disable = too-many-try-statements
            while True:
                time_to_sleep_s = min((time_left_s, 1))
                time.sleep(time_to_sleep_s)
                time_left_s -= 1
                if time_left_s <= 0:
                    break
        except KeyboardInterrupt:
            print("Received keyboard interrupt; exiting")
            break
