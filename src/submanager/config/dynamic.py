"""Load, render, generate and saving of the dynamic config file."""

# Future imports
from __future__ import annotations

# Standard library
import copy
from pathlib import Path

# Local imports
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
    for thread_key, thread_config in (
            static_config.thread_manager.items.items()):
        thread_manager_items[thread_key] = {
            **dict(thread_config.initial),
            **thread_manager_items.get(thread_key, {}),
            }

    dynamic_config = submanager.models.config.DynamicConfig.parse_obj(
        dynamic_config_raw)
    return dynamic_config


def load_dynamic_config(
        static_config: submanager.models.config.StaticConfig,
        config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
        ) -> submanager.models.config.DynamicConfig:
    """Load manager's dynamic runtime config file, creating it if needed."""
    config_path = Path(config_path)
    if not config_path.exists():
        dynamic_config = render_dynamic_config(
            static_config=static_config, dynamic_config_raw={})
        submanager.config.utils.write_config(
            dynamic_config, config_path=config_path)
    else:
        dynamic_config_raw = dict(
            submanager.config.utils.load_config(config_path))
        dynamic_config = render_dynamic_config(
            static_config=static_config, dynamic_config_raw=dynamic_config_raw)

    return dynamic_config
