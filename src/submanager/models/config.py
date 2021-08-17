# static analysis: ignore
"""Core configuration models for the package."""


# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import datetime
import re
from pathlib import (
    Path,
)
from typing import (
    Any,
    Mapping,
    MutableMapping,
    NewType,
    Sequence,
    Union,
)

# Third party imports
import dateutil.relativedelta
import pydantic
from typing_extensions import (
    Final,
    Literal,
)

# Local imports
import submanager.enums
import submanager.models.base
import submanager.models.utils
from submanager.constants import (
    CONFIG_PATH_DYNAMIC,
    CONFIG_PATH_STATIC,
)
from submanager.models.types import (
    NonEmptyStr,
    StripStr,
    StrPattern,
    ThreadIDStr,
)

# ---- Module-level constants ----

DEFAULT_REDIRECT_TEMPLATE: Final[
    str
] = """
This thread is no longer being updated, and has been replaced by:

# [{post_title}]({thread_url})
"""  # noqa: E800


# ---- Standalone models ----


class ConfigPaths(submanager.models.base.CustomBaseModel):
    """Configuration path object for the various config file types."""

    dynamic: Path = CONFIG_PATH_DYNAMIC
    static: Path = CONFIG_PATH_STATIC


# ---- Config common sub-models


class MenuConfig(submanager.models.base.CustomBaseModel):
    """Configuration to parse the menu data from Markdown text."""

    split: NonEmptyStr = "\n\n"
    subsplit: NonEmptyStr = "\n"

    # Work around Pydantic bug at runtime subscripting re.Pattern
    pattern_title: StrPattern = re.compile(r"\[([^\n\]]*)\]\(")
    pattern_url: StrPattern = re.compile(r"\]\(([^\s\)]*)[\s\)]")
    pattern_subtitle: StrPattern = re.compile(r"\[([^\n\]]*)\]\(")


class PatternConfig(submanager.models.base.CustomBaseModel):
    """Configuration for the section pattern-matching."""

    pattern: Union[pydantic.StrictStr, Literal[False]] = False
    pattern_end: pydantic.StrictStr = " End"
    pattern_start: pydantic.StrictStr = " Start"


class InitialThreadConfig(submanager.models.base.CustomBaseModel):
    """Initial configuration of a managed thread."""

    thread_id: Union[Literal[False], ThreadIDStr] = False
    thread_number: pydantic.NonNegativeInt = 0


# ---- Endpoint models ----


class EndpointConfig(submanager.models.base.ItemWithContextConfig):
    """Config params specific to sync endpoint setup."""

    endpoint_name: StripStr


class EndpointTypeConfig(EndpointConfig):
    """Endpoint config including an endpoint type."""

    endpoint_type: submanager.enums.EndpointType = (
        submanager.enums.EndpointType.WIKI_PAGE
    )


class FullEndpointConfig(EndpointTypeConfig, PatternConfig):
    """Config params for a sync source/target endpoint."""

    menu_config: MenuConfig = MenuConfig()
    replace_patterns: Mapping[NonEmptyStr, pydantic.StrictStr] = {}
    truncate_lines: Union[pydantic.PositiveInt, Literal[False]] = False


# ---- Sync manager models ----


class SyncItemConfig(submanager.models.base.ItemConfig):
    """Configuration object for a sync pair of a source and target(s)."""

    source: FullEndpointConfig
    targets: Mapping[StripStr, FullEndpointConfig]

    @pydantic.validator("targets")
    def check_has_targets(  # pylint: disable = no-self-use, no-self-argument
        cls,
        value: Mapping[StripStr, FullEndpointConfig],
    ) -> Mapping[StripStr, FullEndpointConfig]:
        """Validate that at least one target is defined for each sync pair."""
        if not value:
            raise ValueError("No targets defined for sync item")
        return value


class SyncManagerConfig(submanager.models.base.ItemManagerConfig):
    """Top-level configuration for the thread management module."""

    items: Mapping[StripStr, SyncItemConfig] = {}


# ---- Thread manager models ----


class ThreadItemConfig(submanager.models.base.ItemWithContextConfig):
    """Configuration for a managed thread item."""

    approve_new: bool = True
    initial: InitialThreadConfig = InitialThreadConfig()
    link_update_pages: Sequence[StripStr] = []
    new_thread_interval: Union[NonEmptyStr, Literal[False]] = "monthly"
    pin_mode: Union[
        submanager.enums.PinMode,
        pydantic.StrictBool,
    ] = submanager.enums.PinMode.AUTO
    post_title_template: StripStr = (
        "{subreddit} Discussion Thread (#{thread_number})"
    )
    redirect_op: bool = True
    redirect_sticky: bool = True
    redirect_template: NonEmptyStr = DEFAULT_REDIRECT_TEMPLATE
    source: FullEndpointConfig
    target_context: submanager.models.base.ContextConfig

    @pydantic.validator("new_thread_interval")
    def check_interval(  # pylint: disable = no-self-use, no-self-argument
        cls,
        raw_interval: str | Literal[False],
    ) -> str | Literal[False]:
        """Convert a time interval to the expected form."""
        if not raw_interval:
            return False
        (
            interval_unit,
            interval_n,
        ) = submanager.models.utils.process_raw_interval(raw_interval)
        if interval_n is None:
            # If a fixed interval, check unit against datetime attributes
            try:
                interval_value: int = getattr(
                    datetime.datetime.now(),
                    interval_unit,
                )
            except AttributeError as error:
                raise ValueError(
                    f"Interval unit {interval_unit} "
                    "must be a datetime attribute",
                ) from error
            if not isinstance(interval_value, int):
                raise TypeError(
                    f"Interval value {interval_value!r} for unit "
                    f"{interval_unit!r} must be an integer, "
                    f"not {type(interval_value)!r}",
                )
        else:
            # If an offset interval, check against relativedelta kwargs
            delta_kwargs: dict[str, int] = {f"{interval_unit}s": interval_n}
            dateutil.relativedelta.relativedelta(
                **delta_kwargs,  # type: ignore[arg-type]
            )
            if interval_n < 1:
                raise ValueError(
                    f"Interval n has invalid nonpositive value {interval_n!r}",
                )
        return raw_interval


class ThreadManagerConfig(submanager.models.base.ItemManagerConfig):
    """Top-level configuration for the thread management module."""

    items: Mapping[StripStr, ThreadItemConfig] = {}


# ---- Overall static config ----


class AccountConfig(submanager.models.base.CustomBaseModel):
    """Configuration for an individual user account."""

    config: Mapping[StripStr, Any] = {}


AccountsConfig = NewType("AccountsConfig", Mapping[StripStr, AccountConfig])


class StaticConfig(submanager.models.base.CustomBaseModel):
    """Model reprisenting the bot's static configuration."""

    check_readonly: bool = True
    repeat_interval_s: pydantic.NonNegativeFloat = 60
    accounts: AccountsConfig
    context_default: submanager.models.base.ContextConfig
    sync_manager: SyncManagerConfig = SyncManagerConfig()
    thread_manager: ThreadManagerConfig = ThreadManagerConfig()

    @pydantic.validator("accounts")
    def check_has_accounts(  # pylint: disable = no-self-use, no-self-argument
        cls,
        value: AccountsConfig,
    ) -> AccountsConfig:
        """Validate that at least one user account is defined."""
        if not value:
            raise ValueError("No user accounts defined")
        return value


# ---- Dynamic config models ----


class DynamicSyncItemConfig(submanager.models.base.DynamicItemConfig):
    """Dynamically-updated configuration for sync pairs."""

    source_timestamp: pydantic.NonNegativeFloat = 0


class DynamicThreadItemConfig(
    DynamicSyncItemConfig,
    InitialThreadConfig,
    allow_mutation=True,
):
    """Dynamically-updated configuration for managed threads."""


class DynamicSyncManagerConfig(
    submanager.models.base.DynamicItemManagerConfig,
):
    """Dynamically updated configuration for the Sync Manager module."""

    items: MutableMapping[StripStr, DynamicSyncItemConfig] = {}


class DynamicThreadManagerConfig(
    submanager.models.base.DynamicItemManagerConfig,
):
    """Dynamically updated configuration for the Thread Manager module."""

    items: MutableMapping[StripStr, DynamicThreadItemConfig] = {}


class DynamicConfig(submanager.models.base.CustomMutableBaseModel):
    """Model reprisenting the current dynamic configuration."""

    sync_manager: DynamicSyncManagerConfig = DynamicSyncManagerConfig()
    thread_manager: DynamicThreadManagerConfig = DynamicThreadManagerConfig()
