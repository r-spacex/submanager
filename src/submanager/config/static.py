"""Load, render, generate and saving of the main static config file."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import copy
import json
import json.decoder
from pathlib import (
    Path,
)
from typing import (
    Collection,
    TypeVar,
)

# Third party imports
import pydantic
import toml
import toml.decoder

# Local imports
import submanager.config.utils
import submanager.exceptions
import submanager.models.config
import submanager.models.example
import submanager.utils.dicthelpers
from submanager.constants import (
    CONFIG_PATH_STATIC,
)
from submanager.types import (
    ConfigDict,
    PathLikeStr,
    StrMap,
)


def fill_static_config_defaults(raw_config: ConfigDict) -> ConfigDict:
    """Fill in the defaults of a raw static config dictionary."""
    context_default: StrMap = raw_config.get("context_default", {})

    sync_defaults: StrMap = submanager.utils.dicthelpers.update_recursive(
        {"context": context_default},
        raw_config.get("sync_manager", {}).pop("defaults", {}),
    )
    sync_item: StrMap

    # Fill the defaults in each sync item
    sync_manager_items = raw_config.get("sync_manager", {}).get("items", {})
    for sync_key, sync_item in sync_manager_items.items():
        sync_defaults_item: StrMap = (
            submanager.utils.dicthelpers.update_recursive(
                sync_defaults,
                sync_item.pop("defaults", {}),
            )
        )
        sync_item["uid"] = f"sync_manager.items.{sync_key}"
        sync_item["source"] = submanager.utils.dicthelpers.update_recursive(
            sync_defaults_item,
            sync_item.get("source", {}),
        )
        sync_item["source"]["uid"] = sync_item["uid"] + ".source"
        target_config: StrMap
        for target_key, target_config in sync_item.get("targets", {}).items():
            target_config.update(
                submanager.utils.dicthelpers.update_recursive(
                    sync_defaults_item,
                    target_config,
                ),
            )
            target_config["uid"] = sync_item["uid"] + f".targets.{target_key}"

    thread_defaults: StrMap = submanager.utils.dicthelpers.update_recursive(
        {"context": context_default},
        raw_config.get("thread_manager", {}).pop("defaults", {}),
    )
    thread: StrMap

    # Fill the defaults in each managed thread
    thread_manager_items = raw_config.get("thread_manager", {}).get(
        "items",
        {},
    )
    for thread_key, thread in thread_manager_items.items():
        thread.update(
            submanager.utils.dicthelpers.update_recursive(
                thread_defaults,
                thread,
            ),
        )
        thread["uid"] = f"thread_manager.items.{thread_key}"
        thread["source"] = submanager.utils.dicthelpers.update_recursive(
            {"context": thread.get("context", {})},
            thread["source"],
        )
        thread["source"]["uid"] = thread["uid"] + ".source"
        thread["target_context"] = {
            **thread.get("context", {}),
            **thread.get("target_context", {}),
        }

    return raw_config


AccountKeyType = TypeVar("AccountKeyType")


def replace_value_with_missing(
    account_key: AccountKeyType,
    valid_account_keys: Collection[str],
) -> AccountKeyType | str | submanager.models.utils.MissingAccount:
    """Replace the value with the sentinel class if not in the collection."""
    if not isinstance(account_key, str):
        return account_key
    if account_key.strip() in valid_account_keys:
        return account_key.strip()
    return submanager.models.utils.MissingAccount(account_key)


def replace_missing_account_keys(raw_config: ConfigDict) -> ConfigDict:
    """Replace missing account keys with a special class for validation."""
    account_keys: Collection[str] = raw_config.get("accounts", {}).keys()
    raw_config = submanager.utils.dicthelpers.process_items_recursive(
        dict(raw_config),
        fn_torun=replace_value_with_missing,
        fn_kwargs={"valid_account_keys": account_keys},
        keys_match={"account"},
    )
    return raw_config


def check_static_config(
    raw_config: ConfigDict,
    config_path: PathLikeStr = CONFIG_PATH_STATIC,
    raise_error: bool = True,
) -> bool:
    """Perform basic validity checks of the loaded static config object."""
    generate_message = "Try using ``submanager generate-config`` to create it"
    if not raw_config:
        if not raise_error:
            return False
        raise submanager.exceptions.ConfigEmptyError(
            config_path,
            message_post=generate_message,
        )

    return True


def render_static_config(
    raw_config: ConfigDict,
) -> submanager.models.config.StaticConfig:
    """Transform the input config into an object with defaults filled in."""
    raw_config = dict(copy.deepcopy(raw_config))
    raw_config = fill_static_config_defaults(raw_config)
    raw_config = replace_missing_account_keys(raw_config)
    static_config = submanager.models.config.StaticConfig.parse_obj(raw_config)
    return static_config


def load_static_config(
    config_path: PathLikeStr = CONFIG_PATH_STATIC,
) -> submanager.models.config.StaticConfig:
    """Load and render manager's static (user) config file."""
    # Load static config
    try:
        raw_config = submanager.config.utils.load_config(config_path)
    except FileNotFoundError as error:
        raise submanager.exceptions.ConfigNotFoundError(config_path) from error
    except (
        json.decoder.JSONDecodeError,
        toml.decoder.TomlDecodeError,
    ) as error:
        raise submanager.exceptions.ConfigParsingError(
            config_path,
            message_post=error,
        ) from error

    check_static_config(raw_config, config_path=config_path, raise_error=True)

    # Render static config
    try:
        static_config = render_static_config(raw_config)
    except pydantic.ValidationError as error:  # noqa: WPS440
        raise submanager.exceptions.ConfigValidationError(
            config_path,
            message_post=error,
        ) from error

    return static_config


def generate_static_config(
    config_path: PathLikeStr = CONFIG_PATH_STATIC,
    *,
    force: bool = False,
    exist_ok: bool = False,
) -> bool:
    """Generate a static config file with the default example settings."""
    config_path = Path(config_path)
    config_exists = config_path.exists()
    if config_exists:
        if not force:
            if exist_ok:
                return True
            raise submanager.exceptions.ConfigExistsError(config_path)

    example_config = submanager.models.example.EXAMPLE_STATIC_CONFIG.dict(
        exclude=submanager.models.example.EXAMPLE_EXCLUDE_FIELDS,
    )
    submanager.config.utils.write_config(
        config=example_config,
        config_path=config_path,
    )
    return config_exists
