"""Load, render, generate and saving of the dynamic config file."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import copy
from pathlib import (
    Path,
)
from types import (
    TracebackType,
)
from typing import (
    ContextManager,
)

# Third party imports
from typing_extensions import (
    Literal,
)

# Local imports
import submanager.config.lock
import submanager.config.utils
import submanager.models.config
from submanager.constants import (
    CONFIG_PATH_DYNAMIC,
)
from submanager.types import (
    ConfigDictDynamic,
    PathLikeStr,
)


def render_dynamic_config(
    static_config: submanager.models.config.StaticConfig,
    dynamic_config_raw: ConfigDictDynamic,
) -> submanager.models.config.DynamicConfig:
    """Generate the dynamic config, filling defaults as needed."""
    dynamic_config_raw = dict(copy.deepcopy(dynamic_config_raw))

    # Fill defaults in dynamic config
    sync_manager = dynamic_config_raw.get("sync_manager", {})
    dynamic_config_raw["sync_manager"] = sync_manager
    sync_manager_items = sync_manager.get("items", {})
    sync_manager["items"] = sync_manager_items
    for item_key in static_config.sync_manager.items:
        sync_manager_items[item_key] = sync_manager_items.get(item_key, {})

    thread_manager = dynamic_config_raw.get("thread_manager", {})
    dynamic_config_raw["thread_manager"] = thread_manager
    thread_manager_items = thread_manager.get("items", {})
    thread_manager["items"] = thread_manager_items
    thread_manager_items_static = static_config.thread_manager.items
    for thread_key, thread_config in thread_manager_items_static.items():
        thread_manager_items[thread_key] = {
            **dict(thread_config.initial),
            **thread_manager_items.get(thread_key, {}),
        }

    dynamic_config = submanager.models.config.DynamicConfig.parse_obj(
        dynamic_config_raw,
    )
    return dynamic_config


def load_dynamic_config(
    static_config: submanager.models.config.StaticConfig,
    config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
) -> submanager.models.config.DynamicConfig:
    """Load manager's dynamic runtime config file, creating it if needed."""
    config_path = Path(config_path)
    if not config_path.exists():
        dynamic_config = render_dynamic_config(
            static_config=static_config,
            dynamic_config_raw={},
        )
        submanager.config.utils.write_config(
            dynamic_config,
            config_path=config_path,
        )
    else:
        dynamic_config_raw = dict(
            submanager.config.utils.load_config(config_path),
        )
        dynamic_config = render_dynamic_config(
            static_config=static_config,
            dynamic_config_raw=dynamic_config_raw,
        )

    return dynamic_config


class LockedandLoadedDynamicConfig(
    ContextManager[submanager.models.config.DynamicConfig],
):
    """Return the dynamic config if and when it can be locked."""

    def __init__(
        self,
        static_config: submanager.models.config.StaticConfig,
        config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
        timeout_s: float = submanager.config.lock.TIMEOUT_S_DEFAULT,
        verbose: bool = False,
    ) -> None:
        self.static_config = static_config
        self.config_path = Path(config_path)
        self.timeout_s = timeout_s
        self.verbose = verbose

    def __enter__(self) -> submanager.models.config.DynamicConfig:
        """Attempt to acquire a lock on a dynamic config file and return it."""
        submanager.config.lock.wait_for_lock(
            config_path=self.config_path,
            raise_error_on_timeout=True,
            timeout_s=self.timeout_s,
            verbose=self.verbose,
        )
        dynamic_config = load_dynamic_config(
            static_config=self.static_config,
            config_path=self.config_path,
        )
        return dynamic_config

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        """Release the lock on the dynamic config."""
        submanager.config.lock.unlock_config(self.config_path)
        return False
