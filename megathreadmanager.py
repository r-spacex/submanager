#!/usr/bin/env python3
"""Generate, pin and update a regular megathread for a subreddit."""

# Future imports
from __future__ import annotations

# Standard library imports
import abc
import argparse
import configparser
import copy
import datetime
import enum
import json
import json.decoder
import os
import re
import sys
import time
import warnings
from pathlib import Path
from typing import (
    Any,
    Callable,  # Import from collections.abc in Python 3.9
    ClassVar,
    Collection,  # Import from collections.abc in Python 3.9
    Dict,  # Not needed in Python 3.9
    List,  # Not needed in Python 3.9
    Mapping,  # Import from collections.abc in Python 3.9
    MutableMapping,  # Import from collections.abc in Python 3.9
    Pattern,  # Import from re in Python 3.9
    Sequence,  # Import from collections.abc in Python 3.9
    Tuple,  # Not needed in Python 3.9
    Type,  # Not needed in Python 3.9
    TYPE_CHECKING,
    TypeVar,
    Union,  # Not needed in Python 3.9
    )
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    Literal,  # Added to typing in Python 3.8
    Protocol,  # Added to typing in Python 3.8
    runtime_checkable,  # Added to typing in Python 3.8
    )

# Third party imports
import dateutil.relativedelta
import praw
import praw.exceptions
import praw.models
import praw.models.base
import praw.models.reddit.submission
import praw.models.reddit.subreddit
import praw.models.reddit.widgets
import praw.models.reddit.wikipage
import praw.reddit
import praw.util.token_manager
import prawcore.exceptions
import pydantic
import toml
import toml.decoder


# ----------------- Constants -----------------

__version__: Final = "0.6.0dev0"

# General constants
SUPPORTED_CONFIG_FORMATS: Final = frozenset({"json", "toml"})
USER_AGENT: Final = f"praw:megathreadmanager:v{__version__} (by u/CAM-Gerlach)"

# Path constants
CONFIG_DIRECTORY: Final = Path("~/.config/megathread-manager").expanduser()
TOKEN_DIRECTORY: Final = CONFIG_DIRECTORY / "refresh_tokens"
CONFIG_PATH_STATIC: Final = CONFIG_DIRECTORY / "config.toml"
CONFIG_PATH_DYNAMIC: Final = CONFIG_DIRECTORY / "config_dynamic.json"
CONFIG_PATH_REFRESH: Final = TOKEN_DIRECTORY / "refresh_token_{key}.txt"

# Exit codes
EXIT_CODE_UNHANDLED_ERROR: Final = 1
EXIT_CODE_USER_ERROR: Final = 3


# ---- Type aliases ----

if TYPE_CHECKING:
    PathLikeStr = Union["os.PathLike[str]", str]
else:
    PathLikeStr = Union[os.PathLike, str]

StrMap = MutableMapping[str, Any]
ExceptTuple = Tuple[Type[Exception], ...]

ChildrenData = List[MutableMapping[str, str]]
SectionData = MutableMapping[str, Union[str, ChildrenData]]
MenuData = List[SectionData]

AccountConfig = MutableMapping[str, str]
AccountsConfig = Mapping[str, AccountConfig]
AccountConfigProcessed = MutableMapping[str, Union[
    str, praw.util.token_manager.FileTokenManager]]
AccountsConfigProcessed = Mapping[str, AccountConfigProcessed]
AccountsMap = Mapping[str, praw.reddit.Reddit]
ConfigDict = Mapping[str, Any]
ConfigDictDynamic = MutableMapping[str, MutableMapping[str, Any]]


# ----------------- General utility boilerplate -----------------

# ---- Misc utility functions and classes ----

def format_error(error: BaseException) -> str:
    """Format an error as a human-readible string."""
    return f"{type(error).__name__}: {error}"


def print_error(error: BaseException) -> None:
    """Print the error in a human-readible format for end users."""
    print(format_error(error))


class VerbosePrinter:
    """Simple wrapper that only prints if verbose is set."""

    def __init__(self, enable: bool = True) -> None:
        self.enable = enable

    def __call__(self, *text: str) -> None:
        """If verbose is set, print the text."""
        if self.enable:
            print(*text)


class FancyPrinter(VerbosePrinter):
    """Simple print wrapper with a few extra features."""

    def __init__(
            self,
            enable: bool = True,
            char: str = "#",
            step: int = 6,
            level: int | None = None,
            sep: str = " ",
            before: str = "",
            after: str = "",
            ) -> None:
        super().__init__(enable=enable)
        self.char = char
        self.step = step
        self.level = level
        self.sep = sep
        self.before = before
        self.after = after

    def wrap_text(self, *text: str, level: int | None) -> str:
        """Wrap the text in the configured char, up to the specified level."""
        text_joined = self.sep.join(text)
        if level and level > 0:
            wrapping = self.char * (level * self.step)
            text_joined = f"{wrapping} {text_joined} {wrapping}"
        text_joined = f"{self.before}{text_joined}{self.after}"
        return text_joined

    def __call__(self, *text: str, level: int | None = None) -> None:
        """Wrap the text at a certain level given the defaults."""
        print(self.wrap_text(*text, level=level))


# Replace with StrEnum in Python 3.10
class StrValueEnum(enum.Enum):
    """Enum whose repr and str and just the values, for easy serialization."""

    def __repr__(self) -> str:
        """Convert enum value to repr."""
        return str(self.value)

    def __str__(self) -> str:
        """Convert enum value to string."""
        return str(self.value)


KeyType = TypeVar("KeyType")


def process_dict_items_recursive(
        dict_toprocess: MutableMapping[KeyType, Any],
        fn_torun: Callable[..., Any],
        fn_kwargs: dict[str, Any] | None = None,
        keys_match: Collection[str] | None = None,
        inplace: bool = False,
        ) -> MutableMapping[KeyType, Any]:
    """Run the passed function for every matching key in the dictionary."""
    if fn_kwargs is None:
        fn_kwargs = {}
    if not inplace:
        dict_toprocess = copy.deepcopy(dict_toprocess)

    def _process_dict_items_inner(
            dict_toprocess: MutableMapping[KeyType, Any],
            fn_torun: Callable[..., Any],
            fn_kwargs: dict[str, Any],
            ) -> None:
        for key, value in dict_toprocess.items():
            if isinstance(value, dict):
                _process_dict_items_inner(
                    dict_toprocess=value,
                    fn_torun=fn_torun,
                    fn_kwargs=fn_kwargs,
                    )
            else:
                if keys_match is None or key in keys_match:
                    dict_toprocess[key] = fn_torun(value, **fn_kwargs)

    _process_dict_items_inner(
        dict_toprocess=dict_toprocess,
        fn_torun=fn_torun,
        fn_kwargs=fn_kwargs,
        )
    return dict_toprocess


def update_dict_recursive(
        base: MutableMapping[KeyType, Any],
        update: MutableMapping[KeyType, Any],
        inplace: bool = False,
        ) -> MutableMapping[KeyType, Any]:
    """Recursively update the given base dict from another dict."""
    if not inplace:
        base = copy.deepcopy(base)
    for update_key, update_value in update.items():
        base_value = base.get(update_key, {})
        if not isinstance(base_value, MutableMapping):
            base[update_key] = update_value
        elif isinstance(update_value, MutableMapping):
            base[update_key] = update_dict_recursive(
                base_value, update_value)
        else:
            base[update_key] = update_value
    return base


# ---- General enum constants ----

@enum.unique
class EndpointType(StrValueEnum):
    """Reprisent the type of sync endpoint on Reddit."""

    MENU = "MENU"
    THREAD = "THREAD"
    WIDGET = "WIDGET"
    WIKI_PAGE = "WIKI_PAGE"


@enum.unique
class PinType(StrValueEnum):
    """Reprisent the type of thread pinning behavior on Reddit."""

    NONE = "NONE"
    BOTTOM = "BOTTOM"
    TOP = "TOP"


# ----------------- Config classes -----------------

# ---- Conversion functions and classes ----

class MissingAccount:
    """Reprisent missing account keys."""

    def __init__(self, key: str) -> None:
        self.key = key

    def __str__(self) -> str:
        """Convert the class to a string."""
        return str(self.key)


def process_raw_interval(raw_interval: str) -> tuple[str, int | None]:
    """Convert a time interval expressed as a string into a standard form."""
    interval_split = raw_interval.strip().split()
    interval_unit = interval_split[-1]
    if len(interval_split) == 1:
        interval_n = None
    else:
        interval_n = int(interval_split[0])
    interval_unit = interval_unit.rstrip("s")
    if interval_unit[-2:] == "ly":
        interval_unit = interval_unit[:-2]
    if interval_unit == "week" and not interval_n:
        interval_n = 1
    return interval_unit, interval_n


# Hack so that mypy interprets the Pydantic validation types correctly
if TYPE_CHECKING:
    NonEmptyStr = str
    StripStr = str
    ItemIDStr = str
    ThreadIDStr = str
else:

    class NonEmptyStr(pydantic.ConstrainedStr):
        """A non-emptry string type."""

        min_length = 1
        strict = True

    class StripStr(NonEmptyStr):
        """A string with whitespace stripped."""

        strip_whitespace = True

    class ItemIDStr(NonEmptyStr):
        """String reprisenting an item ID in the config dict."""

        regex = re.compile(r"[a-zA-Z0-9_\.]+")

    class ThreadIDStr(StripStr):
        """Pydantic type class for a thread ID of exactly 6 characters."""

        max_length = 6
        min_length = 6
        regex = re.compile(r"[a-z0-9]+")
        to_lower = True


# ---- Pydantic models ----

DEFAULT_REDIRECT_TEMPLATE: Final = """
This thread is no longer being updated, and has been replaced by:

# [{post_title}]({thread_url})
"""


class CustomBaseModel(
        pydantic.BaseModel,
        validate_all=True,
        extra=pydantic.Extra.forbid,
        allow_mutation=False,
        validate_assignment=True,
        ):
    """Local customized Pydantic BaseModel."""


class CustomMutableBaseModel(CustomBaseModel, allow_mutation=True):
    """Custom BaseModel that allows mutation."""


class ConfigPaths(CustomBaseModel):
    """Configuration path object for the various config file types."""

    dynamic: Path = CONFIG_PATH_DYNAMIC
    refresh: Path = CONFIG_PATH_REFRESH
    static: Path = CONFIG_PATH_STATIC


class ItemConfig(CustomBaseModel):
    """Base class for an atomic unit in the config hiearchy."""

    description: pydantic.StrictStr = ""
    enabled: bool = True
    uid: ItemIDStr


class MenuConfig(CustomBaseModel):
    """Configuration to parse the menu data from Markdown text."""

    split: NonEmptyStr = "\n\n"
    subsplit: NonEmptyStr = "\n"
    if TYPE_CHECKING:
        pattern_title: re.Pattern[str] = re.compile(
            r"\[([^\n\]]*)\]\(")
        pattern_url: re.Pattern[str] = re.compile(
            r"\]\(([^\s\)]*)[\s\)]")
        pattern_subtitle: re.Pattern[str] = re.compile(
            r"\[([^\n\]]*)\]\(")
    else:
        pattern_title: Pattern = re.compile(
            r"\[([^\n\]]*)\]\(")
        pattern_url: Pattern = re.compile(
            r"\]\(([^\s\)]*)[\s\)]")
        pattern_subtitle: Pattern = re.compile(
            r"\[([^\n\]]*)\]\(")


class PatternConfig(CustomBaseModel):
    """Configuration for the section pattern-matching."""

    pattern: Union[pydantic.StrictStr, Literal[False]] = False
    pattern_end: pydantic.StrictStr = " End"
    pattern_start: pydantic.StrictStr = " Start"


class ContextConfig(CustomBaseModel):
    """Local context configuration for the bot."""

    account: StripStr
    subreddit: StripStr

    @pydantic.validator("account", pre=True)
    def check_account_found(  # pylint: disable = no-self-use, no-self-argument
            cls, value: MissingAccount | str) -> str:
        """Check that the account is present in the global accounts table."""
        if isinstance(value, MissingAccount):
            raise ValueError(
                f"Account key '{value!s}' not listed in accounts table")
        return value


class EndpointConfig(ItemConfig):
    """Config params specific to sync endpoint setup."""

    context: ContextConfig
    endpoint_name: StripStr


class EndpointTypeConfig(EndpointConfig):
    """Endpoint config including an endpoint type."""

    endpoint_type: EndpointType = EndpointType.WIKI_PAGE


class FullEndpointConfig(EndpointTypeConfig, PatternConfig):
    """Config params for a sync source/target endpoint."""

    enabled: bool = True
    menu_config: MenuConfig = MenuConfig()
    replace_patterns: Mapping[NonEmptyStr, pydantic.StrictStr] = {}


class SyncPairConfig(ItemConfig):
    """Configuration object for a sync pair of a source and target(s)."""

    source: FullEndpointConfig
    targets: Mapping[StripStr, FullEndpointConfig]

    @pydantic.validator("targets")
    def check_targets(  # pylint: disable = no-self-use, no-self-argument
            cls, value: Mapping[StripStr, FullEndpointConfig]
            ) -> Mapping[StripStr, FullEndpointConfig]:
        """Validate that at least one target is defined for each sync pair."""
        if not value:
            raise ValueError("No targets defined for sync pair")
        return value


class SyncConfig(CustomBaseModel):
    """Top-level configuration for the thread management module."""

    enabled: bool = True
    pairs: Mapping[StripStr, SyncPairConfig] = {}


class InitialThreadConfig(CustomBaseModel):
    """Initial configuration of a managed thread."""

    thread_id: Union[Literal[False], ThreadIDStr] = False
    thread_number: pydantic.NonNegativeInt = 0


class ThreadConfig(ItemConfig):
    """Configuration for a managed thread item."""

    approve_new: bool = True
    context: ContextConfig
    initial: InitialThreadConfig = InitialThreadConfig()
    link_update_pages: List[StripStr] = []
    new_thread_interval: Union[NonEmptyStr, Literal[False]] = "monthly"
    new_thread_redirect_op: bool = True
    new_thread_redirect_sticky: bool = True
    new_thread_redirect_template: NonEmptyStr = DEFAULT_REDIRECT_TEMPLATE
    pin_thread: Union[PinType, pydantic.StrictBool] = PinType.BOTTOM
    post_title_template: StripStr = "{subreddit} Megathread (#{thread_number})"
    source: FullEndpointConfig
    target_context: ContextConfig

    @pydantic.validator("new_thread_interval")
    def check_interval(  # pylint: disable = no-self-use, no-self-argument
            cls, raw_interval: str | Literal[False],
            ) -> str | Literal[False]:
        """Convert a time interval to the expected form."""
        if not raw_interval:
            return False
        interval_unit, interval_n = process_raw_interval(raw_interval)
        if interval_n is None:
            try:
                interval_value: int = getattr(
                    datetime.datetime.now(), interval_unit)
            except AttributeError as error:
                raise ValueError(
                    f"Interval unit {interval_unit} "
                    "must be a datetime attribute") from error
            if not isinstance(interval_value, int):
                raise TypeError(
                    f"Interval value {interval_value!r} for unit "
                    f"{interval_unit!r} must be an integer, "
                    f"not {type(interval_value)!r}")
        else:
            delta_kwargs: dict[str, int] = {f"{interval_unit}s": interval_n}
            dateutil.relativedelta.relativedelta(
                **delta_kwargs)  # type: ignore[arg-type]
            if interval_n < 1:
                raise ValueError(
                    f"Interval n has invalid nonpositive value {interval_n!r}")
        return raw_interval


class ThreadsConfig(CustomBaseModel):
    """Top-level configuration for the thread management module."""

    enabled: bool = True
    megathreads: Mapping[StripStr, ThreadConfig] = {}


class StaticConfig(CustomBaseModel):
    """Model reprisenting the bot's static configuration."""

    repeat_interval_s: pydantic.NonNegativeFloat = 60
    accounts: AccountsConfig
    context_default: ContextConfig
    megathread: ThreadsConfig = ThreadsConfig()
    sync: SyncConfig = SyncConfig()

    @pydantic.validator("accounts")
    def check_accounts(  # pylint: disable = no-self-use, no-self-argument
            cls, value: AccountsConfig) -> AccountsConfig:
        """Validate that at least one user account is defined."""
        if not value:
            raise ValueError("No Reddit user accounts defined")
        for account_key, account_kwargs in value.items():
            if not account_kwargs:
                raise ValueError(
                    f"No parameters defined for account {account_key!r}")
        return value


class DynamicSyncConfig(CustomMutableBaseModel):
    """Dynamically-updated configuration for sync pairs."""

    source_timestamp: pydantic.NonNegativeFloat = 0


class DynamicThreadConfig(
        DynamicSyncConfig, InitialThreadConfig, allow_mutation=True):
    """Dynamically-updated configuration for managed threads."""


class DynamicConfig(CustomMutableBaseModel):
    """Model reprisenting the current dynamic configuration."""

    megathread: Dict[StripStr, DynamicThreadConfig] = {}
    sync: Dict[StripStr, DynamicSyncConfig] = {}


# ---- Example config ----

EXAMPLE_ACCOUNT_NAME: Final = "EXAMPLE_USER"

EXAMPLE_ACCOUNT_CONFIG: Final[AccountConfig] = {
    "site_name": "EXAMPLE_SITE_NAME",
    }

EXAMPLE_ACCOUNTS: Final[AccountsConfig] = {
    EXAMPLE_ACCOUNT_NAME: EXAMPLE_ACCOUNT_CONFIG,
    }

EXAMPLE_CONTEXT: Final = ContextConfig(
    account="EXAMPLE_USER",
    subreddit="EXAMPLESUBREDDIT",
    )

EXAMPLE_SOURCE: Final = FullEndpointConfig(
    context=EXAMPLE_CONTEXT,
    description="Example sync source",
    endpoint_name="EXAMPLE_SOURCE_NAME",
    replace_patterns={"https://old.reddit.com": "https://www.reddit.com"},
    uid="EXAMPLE_SOURCE",
    )

EXAMPLE_TARGET: Final = FullEndpointConfig(
    context=EXAMPLE_CONTEXT,
    description="Example sync target",
    endpoint_name="EXAMPLE_TARGET_NAME",
    uid="EXAMPLE_TARGET",
    )

EXAMPLE_SYNC_PAIR: Final = SyncPairConfig(
    description="Example sync pair",
    enabled=False,
    source=EXAMPLE_SOURCE,
    targets={"EXAMPLE_TARGET": EXAMPLE_TARGET},
    uid="EXAMPLE_SYNC_PAIR",
    )


EXAMPLE_THREAD: Final = ThreadConfig(
    context=EXAMPLE_CONTEXT,
    description="Example managed thread",
    enabled=False,
    source=EXAMPLE_SOURCE,
    target_context=EXAMPLE_CONTEXT,
    uid="EXAMPLE_THREAD",
    )


EXAMPLE_STATIC_CONFIG: Final = StaticConfig(
    accounts=EXAMPLE_ACCOUNTS,
    context_default=EXAMPLE_CONTEXT,
    megathread=ThreadsConfig(megathreads={"EXAMPLE_THREAD": EXAMPLE_THREAD}),
    sync=SyncConfig(pairs={"EXAMPLE_SYNC_PAIR": EXAMPLE_SYNC_PAIR}),
    )


EXAMPLE_EXCLUDE_FIELDS: Final[Mapping[str | int, Any]] = {
    "megathread": {
        "megathreads": {
            "EXAMPLE_THREAD": {
                "context": ...,
                "source": {"context", "uid"},
                "target_context": ...,
                "uid": ...,
                },
            },
        },
    "sync": {
        "pairs": {
            "EXAMPLE_SYNC_PAIR": {
                "source": {"context", "uid"},
                "target": {"context", "uid"},
                "uid": ...,
                },
            },
        },
    }


# ----------------- Pattern matching utility functions -----------------

def replace_patterns(text: str, patterns: Mapping[str, str]) -> str:
    """Replace each pattern in the text with its mapped replacement."""
    for old, new in patterns.items():
        text = text.replace(old, new)
    return text


def startend_to_pattern(start: str, end: str | None = None) -> str:
    """Convert a start and end string to capture everything between."""
    end = start if end is None else end
    pattern = r"(?<={start})(\s|\S)*(?={end})".format(
        start=re.escape(start), end=re.escape(end))
    return pattern


def startend_to_pattern_md(start: str, end: str | None = None) -> str:
    """Convert start/end strings to a Markdown-"comment" capture pattern."""
    end = start if end is None else end
    start, end = [f"[](/# {pattern})" for pattern in (start, end)]
    return startend_to_pattern(start, end)


def search_startend(
        source_text: str,
        pattern: str | Literal[False] | None = "",
        start: str = "",
        end: str = "",
        ) -> re.Match[str] | Literal[False] | None:
    """Match the text between the given Markdown pattern w/suffices."""
    if pattern is False or pattern is None or not (pattern or start or end):
        return False
    start = pattern + start
    end = pattern + end
    pattern = startend_to_pattern_md(start, end)
    match_obj = re.search(pattern, source_text)
    return match_obj


def split_and_clean_text(source_text: str, split: str) -> list[str]:
    """Split the text into sections and strip each individually."""
    source_text = source_text.strip()
    if split:
        sections = source_text.split(split)
    else:
        sections = [source_text]
    sections = [section.strip() for section in sections if section.strip()]
    return sections


def extract_text(
        pattern: re.Pattern[str] | str,
        source_text: str,
        ) -> str | Literal[False]:
    """Match the given pattern and extract the matched text as a string."""
    match = re.search(pattern, source_text)
    if not match:
        return False
    match_text = match.groups()[0] if match.groups() else match.group()
    return match_text


# ----------------- Sync endpoint classes -----------------

@runtime_checkable
class EditableTextWidgetModeration(Protocol):
    """Widget moderation object with editable text."""

    @abc.abstractmethod
    def update(self, text: str) -> None:
        """Update method that takes a string."""
        raise NotImplementedError


@runtime_checkable
class EditableTextWidget(Protocol):
    """An object with text that can be edited."""

    mod: EditableTextWidgetModeration
    text: str


@runtime_checkable
class RevisionDateCheckable(Protocol):
    """An object with a retrievable revision date."""

    @property
    @abc.abstractmethod
    def revision_date(self) -> int:
        """Get the date the sync endpoint was last updated."""
        raise NotImplementedError


class SyncEndpoint(metaclass=abc.ABCMeta):
    """Abstraction of a source or target for a Reddit sync action."""

    @abc.abstractmethod
    def _setup_object(self) -> object:
        """Set up the underlying PRAW object the endpoint will use."""
        raise NotImplementedError

    def _validate_object(self) -> None:
        """Validate the the object exits and has the needed properties."""
        try:
            self.content
        except PRAW_NOTFOUND_ERRORS as error:
            raise RedditObjectNotFoundError(
                self.config,
                message_pre=(f"Reddit object {self._object!r} not found"),
                message_post=error,
                ) from error
        except PRAW_FORBIDDEN_ERRORS as error:
            raise RedditObjectNotAccessibleError(
                self.config,
                message_pre=(
                    f"Reddit object {self._object!r} found but not accessible "
                    f"from account {self.config.context.account!r}"),
                message_post=error,
                ) from error

    def __init__(
            self,
            config: EndpointConfig,
            reddit: praw.reddit.Reddit,
            validate: bool = False,
            raise_error: bool = True,
            ) -> None:
        self.config = config
        self._reddit = reddit
        self._validated: bool | None = None

        self._subreddit: praw.models.reddit.subreddit.Subreddit = (
            self._reddit.subreddit(self.config.context.subreddit))
        try:
            self._subreddit.id
        except PRAW_NOTFOUND_ERRORS as error:
            raise SubredditNotFoundError(
                self.config,
                message_pre=(
                    f"Sub 'r/{self.config.context.subreddit}' not found"),
                message_post=error,
                ) from error
        except PRAW_FORBIDDEN_ERRORS as error:
            raise SubredditNotAccessibleError(
                self.config,
                message_pre=(
                    f"Sub 'r/{self.config.context.subreddit}' found but not "
                    f"accessible from current account "
                    f"{self.config.context.account!r}"),
                message_post=error,
                ) from error

        self._object = self._setup_object()
        if validate:
            self._validated = self.validate(raise_error=raise_error)

    @property
    @abc.abstractmethod
    def content(self) -> str | MenuData:
        """Get the current content of the sync endpoint."""
        raise NotImplementedError

    @abc.abstractmethod
    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the sync endpoint with the given content."""
        raise NotImplementedError

    @abc.abstractmethod
    def _check_is_editable(self, raise_error: bool = True) -> bool:
        """Check if the object can be edited by the user, w/o validation."""

    def check_is_editable(self, raise_error: bool = True) -> bool | None:
        """Check if the object can be edited by the user, with validation."""
        if self._validated is None or (
                self._validated is False and raise_error):
            self.validate(raise_error=raise_error)
        if not self.is_valid:
            return None
        return self._check_is_editable(raise_error=raise_error)

    @property
    def is_editable(self) -> bool | None:
        """Is True if the object is editable by the user, False otherwise."""
        return self.check_is_editable(raise_error=False)

    @property
    def is_valid(self) -> bool:
        """Is true if the object is validated, false if not."""
        if self._validated is None:
            return self.validate(raise_error=False)
        return self._validated

    def validate(self, raise_error: bool = True) -> bool:
        """Validate that the sync endpoint points to a valid Reddit object."""
        try:
            self._validate_object()
        except RedditError:
            self._validated = False
            if not raise_error:
                return False
            raise
        else:
            self._validated = True
            return True


class WidgetSyncEndpoint(SyncEndpoint, metaclass=abc.ABCMeta):
    """Sync endpoint reprisenting a generic New Reddit widget."""

    _object: praw.models.reddit.widgets.Widget | EditableTextWidget

    @abc.abstractmethod
    def _setup_object(
            self) -> praw.models.reddit.widgets.Widget | EditableTextWidget:
        """Set up the underlying PRAW object the endpoint will use."""
        raise NotImplementedError

    def _check_is_editable(self, raise_error: bool = True) -> bool:
        """Is True if the widget is editable, False otherwise."""
        try:
            self._object.mod.update()  # type: ignore[call-arg]
        except prawcore.exceptions.Forbidden as error:
            if not raise_error:
                return False
            raise NotAModError(
                self.config,
                message_pre=(f"Account {self.config.context.account!r} must "
                             "be a moderator to update widgets"),
                message_post=error,
                ) from error
        else:
            return True


class MenuSyncEndpoint(WidgetSyncEndpoint):
    """Sync endpoint reprisenting a New Reddit top bar menu widget."""

    _object: praw.models.reddit.widgets.Menu

    def _setup_object(self) -> praw.models.reddit.widgets.Menu:
        """Set up the menu widget object for syncing to a menu."""
        widgets = self._subreddit.widgets.topbar
        for widget in widgets:
            if isinstance(widget, praw.models.reddit.widgets.Menu):
                return widget
        raise RedditObjectNotFoundError(
            self.config,
            message_pre=("Menu widget not found in "
                         f"'r/{self.config.context.subreddit}'"),
            message_post=(
                "You may need to create it by adding at least one menu item."),
            )

    @property
    def content(self) -> MenuData:
        """Get the current structured data in the menu widget."""
        attribute_name = "data"
        menu_data: MenuData | None = getattr(
            self._object, attribute_name, None)
        if menu_data is None:
            raise RedditModelError(
                self.config,
                message_pre=(f"Menu widget {self._object!r} "
                             f"missing attribute {attribute_name!r}"),
                )
        return menu_data

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the menu with the given structured data."""
        self._object.mod.update(data=new_content)


class ThreadSyncEndpoint(SyncEndpoint, RevisionDateCheckable):
    """Sync endpoint reprisenting a Reddit thread (selfpost submission)."""

    _object: praw.models.reddit.submission.Submission

    def _setup_object(self) -> praw.models.reddit.submission.Submission:
        """Set up the submission object for syncing to a thread."""
        submission: praw.models.reddit.submission.Submission = (
            self._reddit.submission(id=self.config.endpoint_name))
        return submission

    @property
    def content(self) -> str:
        """Get the current submission's selftext."""
        submission_text: str = self._object.selftext
        return submission_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the thread's text to be that passed."""
        self._object.edit(str(new_content))

    def _check_is_editable(self, raise_error: bool = True) -> bool:
        """Is True if the thread is editable, False otherwise."""
        try:
            self.edit(self.content)
        except prawcore.exceptions.Forbidden as error:
            if not raise_error:
                return False
            raise NotOPError(
                self.config,
                message_pre=(
                    f"Account {self.config.context.account!r} used to edit "
                    f"the post {self._object.title!r} ({self._object.id}) "
                    f"must be the OP {self._object.author.name!r}"),
                message_post=error,
                ) from error
        except praw.exceptions.RedditAPIException as error:
            for reddit_error in error.items:
                if reddit_error.error_type.lower().strip() == "placeholder":
                    if not raise_error:
                        return False
                    raise PostTypeError(
                        self.config,
                        message_pre=(
                            f"Cannot edit link post {self._object.title!r} "
                            f"({self._object.id}); must be a selfpost"),
                        message_post=error,
                        ) from error
            raise
        else:
            return True

    @property
    def revision_date(self) -> int:
        """Get the date the thread was last edited."""
        edited_date: int | Literal[False] = self._object.edited
        if not edited_date:
            edited_date = self._object.created_utc
        return edited_date


class SidebarWidgetSyncEndpoint(WidgetSyncEndpoint):
    """Sync endpoint reprisenting a New Reddit sidebar text content widget."""

    _object: EditableTextWidget

    def _setup_object(self) -> EditableTextWidget:
        """Set up the widget object for syncing to a sidebar widget."""
        widgets = self._subreddit.widgets.sidebar
        names: list[str] = []
        for widget in widgets:
            widget_name: str | None = getattr(widget, "shortName", None)
            if not widget_name:
                continue
            if widget_name == self.config.endpoint_name:
                if isinstance(widget, EditableTextWidget):
                    return widget
                raise WidgetTypeError(
                    self.config,
                    message_pre=(f"Widget {self.config.endpoint_name!r} "
                                 f"has unsupported type {type(widget)!r}"),
                    message_post=(
                        "Only text-content widgets are currently supported."),
                    )
            names.append(widget_name)
        raise RedditObjectNotFoundError(
            self.config,
            message_pre=(f"Sidebar widget {self.config.endpoint_name!r} "
                         f"not found in 'r/{self.config.context.subreddit}' "
                         f"(found widgets: {names if names else 'None'!s})"),
            message_post="If this is not a typo, please create it first.",
            )

    @property
    def content(self) -> str:
        """Get the current text content of the sidebar widget."""
        widget_text: str = self._object.text
        return widget_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the sidebar widget with the given text content."""
        self._object.mod.update(text=str(new_content))


class WikiSyncEndpoint(SyncEndpoint, RevisionDateCheckable):
    """Sync endpoint reprisenting a Reddit wiki page."""

    _object: praw.models.reddit.wikipage.WikiPage

    def _setup_object(self) -> praw.models.reddit.wikipage.WikiPage:
        """Set up the wiki page object for syncing to a wiki page."""
        wiki_page: praw.models.reddit.wikipage.WikiPage = (
            self._subreddit.wiki[self.config.endpoint_name])
        return wiki_page

    @property
    def content(self) -> str:
        """Get the current text content of the wiki page."""
        wiki_text: str = self._object.content_md
        return wiki_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the wiki page with the given text."""
        self._object.edit(str(new_content), reason=reason)

    def _check_is_editable(self, raise_error: bool = True) -> bool:
        """Is True if the wiki page is editable, False otherwise."""
        try:
            self.edit(self.content, reason="Validation edit from Sub Manager")
        except (prawcore.exceptions.Forbidden,
                praw.exceptions.RedditAPIException) as error:
            if isinstance(error, praw.exceptions.RedditAPIException):
                for reddit_error in error.items:
                    if reddit_error.error_type.upper() == "WIKI_CREATE_ERROR":
                        break
                else:
                    raise
            if not raise_error:
                return False
            raise WikiPagePermissionError(
                self.config,
                message_pre=(f"Account {self.config.context.account!r} "
                             "must be authorized to access wiki page "
                             f"{self.config.endpoint_name!r}"),
                message_post=error,
                ) from error
        else:
            return True

    @property
    def revision_date(self) -> int:
        """Get the date the wiki page was last updated."""
        revision_timestamp: int = self._object.revision_date
        return revision_timestamp


SYNC_ENDPOINT_TYPES: Final[Mapping[EndpointType, type[SyncEndpoint]]] = {
    EndpointType.MENU: MenuSyncEndpoint,
    EndpointType.THREAD: ThreadSyncEndpoint,
    EndpointType.WIDGET: SidebarWidgetSyncEndpoint,
    EndpointType.WIKI_PAGE: WikiSyncEndpoint,
    }


def create_sync_endpoint_from_config(
        config: EndpointTypeConfig,
        reddit: praw.reddit.Reddit,
        validate: bool = False,
        raise_error: bool = True,
        ) -> SyncEndpoint:
    """Create a new sync endpoint given a particular config and Reddit obj."""
    sync_endpoint = SYNC_ENDPOINT_TYPES[config.endpoint_type](
        config=config,
        reddit=reddit,
        validate=validate,
        raise_error=raise_error,
        )
    return sync_endpoint


# ----------------- Errors and exceptions -----------------

PRAW_NOTFOUND_ERRORS: Final[ExceptTuple] = (
    prawcore.exceptions.NotFound,
    prawcore.exceptions.Redirect,
    )

PRAW_FORBIDDEN_ERRORS: Final[ExceptTuple] = (
    prawcore.exceptions.Forbidden,
    prawcore.exceptions.UnavailableForLegalReasons,
    )

PRAW_RETRIVAL_ERRORS: Final[ExceptTuple] = (
    *PRAW_NOTFOUND_ERRORS,
    *PRAW_FORBIDDEN_ERRORS,
    )

PRAW_AUTHORIZATION_ERRORS: Final[ExceptTuple] = (
    praw.exceptions.InvalidImplicitAuth,
    praw.exceptions.ReadOnlyException,
    prawcore.exceptions.Forbidden,
    prawcore.exceptions.InsufficientScope,
    prawcore.exceptions.InvalidToken,
    prawcore.exceptions.OAuthException,
    )

PRAW_REDDIT_ERRORS: Final[ExceptTuple] = (
    praw.exceptions.RedditAPIException,
    prawcore.exceptions.ResponseException,
    )

PRAW_ALL_ERRORS: Final[ExceptTuple] = (
    praw.exceptions.PRAWException,
    prawcore.exceptions.PrawcoreException,
    configparser.Error,
    )


# ---- Base exception classes

class SubManagerError(Exception):
    """Base class for errors raised by Sub Manager."""

    def __init__(
            self,
            message: str,
            message_pre: str | None = None,
            message_post: str | BaseException | None = None,
            ) -> None:
        message = message.strip(" ")
        if message_pre:
            message = f"{message_pre.strip(' ')} {message}"
        if message_post is not None:
            if isinstance(message_post, BaseException):
                message_post = format_error(message_post)
            message = f"{message}\n\n{message_post.strip(' ')}"
        super().__init__(message)


class ErrorFillable(SubManagerError, metaclass=abc.ABCMeta):
    """Error with a fillable message."""

    _message_pre: ClassVar[str] = "Error"
    _message_template: ClassVar[str] = "occured"

    def __init__(
            self,
            message_pre: str | None = None,
            message_post: str | BaseException | None = None,
            **extra_fillables: str,
            ) -> None:
        if message_pre is None:
            message_pre = self._message_pre
        message = self._message_template.format(**extra_fillables)
        super().__init__(
            message=message,
            message_pre=message_pre,
            message_post=message_post,
            )


class ErrorWithConfigItem(ErrorFillable):
    """Something's wrong with an endpoint."""

    _message_pre: ClassVar[str] = "Error"
    _message_template: ClassVar[str] = "in item {config}"

    def __init__(
            self,
            config_item: ItemConfig,
            message_pre: str | None = None,
            message_post: str | BaseException | None = None,
            **extra_fillables: str,
            ) -> None:
        self.config_item = config_item
        super().__init__(
            message_pre=message_pre,
            message_post=message_post,
            config=f"{config_item.uid} - {config_item.description!r}",
            **extra_fillables)


class SubManagerValueError(SubManagerError, ValueError):
    """General programmer errors related to values not being as expected."""


class SubManagerUserError(SubManagerError):
    """Errors at runtime that should be correctable via user action."""


# ---- Reddit-related exceptions ----

class RedditError(SubManagerError):
    """Something went wrong with the data returned from the Reddit API."""


class RedditObjectNotFoundError(
        ErrorWithConfigItem, RedditError, SubManagerUserError):
    """Could not find the object on Reddit."""


class SubredditNotFoundError(RedditObjectNotFoundError):
    """Could not access subreddit due to name being not found or blocked."""


class RedditModelError(ErrorWithConfigItem, RedditError):
    """The object's data model didn't match that required."""


class PostTypeError(ErrorWithConfigItem, RedditError, SubManagerUserError):
    """The post was found, but it was of the wrong type (link/self)."""


class WidgetTypeError(ErrorWithConfigItem, RedditError, SubManagerUserError):
    """A widget was found with the given name, but is of unsupported type."""


# ---- Permissions exceptions ----

class RedditPermissionError(RedditError, SubManagerUserError):
    """Errors related to not having Reddit permissions to perform an action."""


class RedditObjectNotAccessibleError(
        ErrorWithConfigItem, RedditPermissionError):
    """Found the object but could not access it with the current account."""


class SubredditNotAccessibleError(RedditObjectNotAccessibleError):
    """Found the subreddit but it was private, quarentined or banned."""


class NotAModError(ErrorWithConfigItem, RedditPermissionError):
    """The user needs to be a moderator to perform the requested action."""


class NotOPError(ErrorWithConfigItem, RedditPermissionError):
    """The user needs to be the post OP to perform the requested action."""


class WikiPagePermissionError(ErrorWithConfigItem, RedditPermissionError):
    """The user is not authorized to edit the given wiki page."""


# ---- Authorization-related exceptions ----

class TestPageNotFoundWarning(DeprecationWarning):
    """A sub/page checked for account authorization was not found."""


class NoTestableScopesWarning(DeprecationWarning):
    """The account didn't have any scopes that could be tested for access."""


class ErrorWithAccount(ErrorFillable):
    """Something's wrong with the Reddit account configuration."""

    _message_pre: ClassVar[str] = "Error"
    _message_template: ClassVar[str] = (
        "with account {account_key!r}")

    def __init__(
            self,
            account_key: str,
            message_pre: str | None = None,
            message_post: str | BaseException | None = None,
            **extra_fillables: str,
            ) -> None:
        self.account_key = account_key
        super().__init__(
            message_pre=message_pre,
            message_post=message_post,
            account_key=account_key,
            **extra_fillables)


class AuthError(RedditError, SubManagerUserError):
    """Errors related to user authentication."""


class AccountCheckError(ErrorWithAccount, RedditError, SubManagerUserError):
    """Cannot perform an operation checking that the account is authorized."""


class AccountCheckAuthError(AccountCheckError, AuthError):
    """Authorization error occured when checking the user account."""


class RedditReadOnlyError(ErrorWithAccount, AuthError):
    """The Reddit instance is not authorized and is thus read-only."""


class NoAuthorizedScopesError(ErrorWithAccount, AuthError):
    """The user has no authorized scopes."""


class InsufficientScopeError(ErrorWithConfigItem, AuthError):
    """The token needs a particular OAUTH scope it wasn't authorized for."""


# ---- Config-related exceptions ----

class ConfigError(SubManagerUserError):
    """There is a problem with the Sub Manager configuration."""


class ConfigErrorWithPath(ErrorFillable, ConfigError):
    """Config errors that involve a config file at a specific path."""

    _message_pre: ClassVar[str] = "Error"
    _message_template: ClassVar[str] = (
        "for config file at path {config_path!r}")

    def __init__(
            self,
            config_path: PathLikeStr,
            message_pre: str | None = None,
            message_post: str | BaseException | None = None,
            **extra_fillables: str,
            ) -> None:
        self.config_path = Path(config_path)
        super().__init__(
            message_pre=message_pre,
            message_post=message_post,
            config_path=self.config_path.as_posix(),
            **extra_fillables)


class ConfigNotFoundError(ConfigErrorWithPath):
    """The Sub Manager configuration file is not found."""

    _message_pre: ClassVar[str] = "File not found"


class ConfigExistsError(ConfigErrorWithPath):
    """The Sub Manager configuration file already exists when generated."""

    _message_pre: ClassVar[str] = "File already exists"


class ConfigTypeError(ConfigErrorWithPath):
    """The Sub Manager config file is not in a recognized format."""

    _message_pre: ClassVar[str] = "Config format type not supported"


class ConfigFormatError(ConfigErrorWithPath):
    """The Sub Manager config file format is not valid."""

    _message_pre: ClassVar[str] = "File format error"


class ConfigValidationError(ConfigErrorWithPath):
    """The Sub Manager config file has invalid property value(s)."""

    _message_pre: ClassVar[str] = "Validation failed"


class ConfigDefaultError(ConfigErrorWithPath):
    """The Sub Manager configuration file has not been configured."""

    _message_pre: ClassVar[str] = "Unconfigured defaults"


class AccountConfigError(ErrorWithAccount, ConfigError):
    """PRAW error loading the Reddit account configuration."""

    _message_pre: ClassVar[str] = "PRAW error on initialization"


# ----------------- Config handling -----------------

# ---- Config utilities ----

def serialize_config(
        config: ConfigDict | pydantic.BaseModel,
        output_format: str = "json",
        ) -> str:
    """Convert the configuration data to a serializable text form."""
    if output_format == "json":
        if isinstance(config, pydantic.BaseModel):
            serialized_config = config.json(indent=4)
        else:
            serialized_config = json.dumps(dict(config), indent=4)
    elif output_format == "toml":
        serialized_config = toml.dumps(dict(config))
    else:
        raise ConfigError(
            f"Output format {output_format!r} must be in "
            f"{SUPPORTED_CONFIG_FORMATS}")
    return serialized_config


def write_config(
        config: ConfigDict | pydantic.BaseModel,
        config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
        ) -> str:
    """Write the passed config to the specified config path."""
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        serialized_config = serialize_config(
            config=config, output_format=config_path.suffix[1:])
    except ConfigError as error:
        raise ConfigTypeError(config_path, message_post=error) from error
    with open(config_path, mode="w",
              encoding="utf-8", newline="\n") as config_file:
        config_file.write(serialized_config)
    return serialized_config


def load_config(config_path: PathLikeStr) -> ConfigDict:
    """Load the config file at the specified path."""
    config_path = Path(config_path)
    with open(config_path, mode="r", encoding="utf-8") as config_file:
        config: ConfigDict
        if config_path.suffix == ".json":
            config = dict(json.load(config_file))
        elif config_path.suffix == ".toml":
            config = dict(toml.load(config_file))
        else:
            raise ConfigTypeError(
                config_path,
                message_post=ConfigError(
                    f"Input format {config_path.suffix!r} must be in "
                    f"{SUPPORTED_CONFIG_FORMATS}"),
                )
    return config


# ---- Static config ----

def fill_static_config_defaults(raw_config: ConfigDict) -> ConfigDict:
    """Fill in the defaults of a raw static config dictionary."""
    context_default: StrMap = raw_config.get("context_default", {})

    sync_defaults: StrMap = update_dict_recursive(
        {"context": context_default},
        raw_config.get("sync", {}).pop("defaults", {}))
    sync_pair: StrMap
    for sync_key, sync_pair in (
            raw_config.get("sync", {}).get("pairs", {}).items()):
        sync_defaults_item: StrMap = update_dict_recursive(
            sync_defaults, sync_pair.pop("defaults", {}))
        sync_pair["uid"] = f"sync.pairs.{sync_key}"
        sync_pair["source"] = update_dict_recursive(
            sync_defaults_item, sync_pair.get("source", {}))
        sync_pair["source"]["uid"] = sync_pair["uid"] + ".source"
        target_config: StrMap
        for target_key, target_config in sync_pair.get("targets", {}).items():
            target_config.update(
                update_dict_recursive(sync_defaults_item, target_config))
            target_config["uid"] = sync_pair["uid"] + f".targets.{target_key}"

    thread_defaults: StrMap = update_dict_recursive(
        {"context": context_default},
        raw_config.get("megathread", {}).pop("defaults", {}))
    thread: StrMap
    for thread_key, thread in (
            raw_config.get("megathread", {}).get("megathreads", {}).items()):
        thread.update(
            update_dict_recursive(thread_defaults, thread))
        thread["uid"] = f"megathread.megathreads.{thread_key}"
        thread["source"] = update_dict_recursive(
            {"context": thread.get("context", {})}, thread["source"])
        thread["source"]["uid"] = thread["uid"] + ".source"
        thread["target_context"] = {
            **thread.get("context", {}), **thread.get("target_context", {})}

    return raw_config


def replace_value_with_missing(
        account_key: str,
        valid_account_keys: Collection[str],
        ) -> str | MissingAccount:
    """Replace the value with the sentinel class if not in the collection."""
    if account_key.strip() in valid_account_keys:
        return account_key.strip()
    return MissingAccount(account_key)


def replace_missing_account_keys(raw_config: ConfigDict) -> ConfigDict:
    """Replace missing account keys with a special class for validation."""
    account_keys: Collection[str] = raw_config.get("accounts", {}).keys()
    raw_config = process_dict_items_recursive(
        dict(raw_config),
        fn_torun=replace_value_with_missing,
        fn_kwargs={"valid_account_keys": account_keys},
        keys_match={"account"},
        )
    return raw_config


def render_static_config(raw_config: ConfigDict) -> StaticConfig:
    """Transform the input config into an object with defaults filled in."""
    raw_config = dict(copy.deepcopy(raw_config))
    raw_config = fill_static_config_defaults(raw_config)
    raw_config = replace_missing_account_keys(raw_config)
    static_config = StaticConfig.parse_obj(raw_config)
    return static_config


def load_static_config(
        config_path: PathLikeStr = CONFIG_PATH_STATIC) -> StaticConfig:
    """Load manager's static (user) config file, creating it if needed."""
    try:
        raw_config = load_config(config_path)
    except FileNotFoundError as error:
        raise ConfigNotFoundError(config_path) from error
    except (
            json.decoder.JSONDecodeError,
            toml.decoder.TomlDecodeError,
            ) as error:
        raise ConfigFormatError(
            config_path, message_post=error) from error
    try:
        static_config = render_static_config(raw_config)
    except pydantic.ValidationError as error:
        raise ConfigValidationError(
            config_path, message_post=error) from error

    return static_config


def generate_static_config(
        config_path: PathLikeStr = CONFIG_PATH_STATIC,
        force: bool = False,
        exist_ok: bool = False,
        ) -> bool:
    """Generate a static config file with the default example settings."""
    config_path = Path(config_path)
    config_exists = config_path.exists()
    if config_exists:
        if exist_ok:
            return config_exists
        if not force:
            raise ConfigExistsError(config_path)

    example_config = EXAMPLE_STATIC_CONFIG.dict(exclude=EXAMPLE_EXCLUDE_FIELDS)
    write_config(config=example_config, config_path=config_path)
    return config_exists


# ---- Dynamic config ----

def render_dynamic_config(
        static_config: StaticConfig,
        dynamic_config_raw: ConfigDictDynamic,
        ) -> DynamicConfig:
    """Generate the dynamic config, filling defaults as needed."""
    dynamic_config_raw = dict(copy.deepcopy(dynamic_config_raw))

    # Fill defaults in dynamic config
    dynamic_config_raw["sync"] = dynamic_config_raw.get("sync", {})
    for pair_key in static_config.sync.pairs:
        dynamic_config_raw["sync"][pair_key] = (
            dynamic_config_raw["sync"].get(pair_key, {}))

    dynamic_config_raw["megathread"] = dynamic_config_raw.get("megathread", {})
    for thread_key, thread_config in (
            static_config.megathread.megathreads.items()):
        dynamic_config_raw["megathread"][thread_key] = {
            **dict(thread_config.initial),
            **dynamic_config_raw["megathread"].get(thread_key, {})}

    dynamic_config = DynamicConfig.parse_obj(dynamic_config_raw)
    return dynamic_config


def load_dynamic_config(
        static_config: StaticConfig,
        config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
        ) -> DynamicConfig:
    """Load manager's dynamic runtime config file, creating it if needed."""
    config_path = Path(config_path)
    if not config_path.exists():
        dynamic_config = render_dynamic_config(
            static_config=static_config, dynamic_config_raw={})
        write_config(dynamic_config, config_path=config_path)
    else:
        dynamic_config_raw = dict(load_config(config_path))
        dynamic_config = render_dynamic_config(
            static_config=static_config, dynamic_config_raw=dynamic_config_raw)

    return dynamic_config


# ----------------- Core megathread logic -----------------

def generate_template_vars(
        thread_config: ThreadConfig,
        dynamic_config: DynamicThreadConfig,
        ) -> dict[str, str | int | datetime.datetime]:
    """Generate the title and post templates."""
    template_vars: dict[str, str | int | datetime.datetime] = {
        "current_datetime": datetime.datetime.now(datetime.timezone.utc),
        "current_datetime_local": datetime.datetime.now(),
        "subreddit": thread_config.context.subreddit,
        "thread_number": dynamic_config.thread_number,
        "thread_number_previous": dynamic_config.thread_number - 1,
        "thread_id_previous":
            "" if not dynamic_config.thread_id else dynamic_config.thread_id,
        }
    template_vars["post_title"] = (
        thread_config.post_title_template.format(**template_vars))
    return template_vars


def update_page_links(
        links: Mapping[str, str],
        pages_to_update: Sequence[str],
        reddit: praw.reddit.Reddit,
        context: ContextConfig,
        uid: str,
        description: str = "",
        ) -> None:
    """Update the links to the given thread on the passed pages."""
    uid_base = ".".join(uid.split(".")[:-1])
    for page_name in pages_to_update:
        page_config = EndpointConfig(
            context=context,
            description=f"Megathread link page {page_name}",
            endpoint_name=page_name,
            uid=uid + f".{page_name}",
            )
        page = WikiSyncEndpoint(
            config=page_config,
            reddit=reddit,
            )
        new_content = page.content
        for old_link, new_link in links.items():
            new_content = re.sub(
                pattern=re.escape(old_link),
                repl=new_link,
                string=new_content,
                flags=re.IGNORECASE,
                )
        page.edit(
            new_content, reason=(
                f"Update {description or uid_base} megathread URLs"))


def create_new_thread(
        thread_config: ThreadConfig,
        dynamic_config: DynamicThreadConfig,
        accounts: AccountsMap,
        ) -> None:
    """Create a new thread based on the title and post template."""
    # Generate thread title and contents
    dynamic_config.source_timestamp = 0
    dynamic_config.thread_number += 1

    # Get subreddit objects for accounts
    reddit_mod = accounts[thread_config.context.account]
    reddit_post = accounts[thread_config.target_context.account]

    source_obj = create_sync_endpoint_from_config(
        config=thread_config.source,
        reddit=accounts[thread_config.source.context.account])

    template_vars = generate_template_vars(thread_config, dynamic_config)
    post_text = process_source_endpoint(
        thread_config.source, source_obj, dynamic_config)

    # Get current thread objects first
    current_thread: praw.models.reddit.submission.Submission | None = None
    current_thread_mod: praw.models.reddit.submission.Submission | None = None
    if dynamic_config.thread_id:
        current_thread = reddit_post.submission(id=dynamic_config.thread_id)
        current_thread_mod = reddit_mod.submission(id=dynamic_config.thread_id)

    # Submit and approve new thread
    new_thread: praw.models.reddit.submission.Submission = (
        reddit_post.subreddit(
            thread_config.target_context.subreddit
            )
        .submit(title=template_vars["post_title"], selftext=post_text)
        )
    new_thread.disable_inbox_replies()  # type: ignore[no-untyped-call]
    new_thread_mod: praw.models.reddit.submission.Submission = (
        reddit_mod.submission(id=new_thread.id))
    if thread_config.approve_new:
        new_thread_mod.mod.approve()
    for attribute in ["id", "url", "permalink", "shortlink"]:
        template_vars[f"thread_{attribute}"] = getattr(new_thread, attribute)

    # Unpin old thread and pin new one
    if thread_config.pin_thread and thread_config.pin_thread != PinType.NONE:
        bottom_sticky = thread_config.pin_thread != PinType.TOP
        if current_thread_mod:
            current_thread_mod.mod.sticky(state=False)
            time.sleep(10)
        sticky_to_keep: praw.models.reddit.submission.Submission | None = None
        try:
            sticky_to_keep = reddit_mod.subreddit(
                thread_config.context.subreddit).sticky(number=1)
            if (current_thread and sticky_to_keep
                    and sticky_to_keep.id == current_thread.id):
                sticky_to_keep = reddit_mod.subreddit(
                    thread_config.context.subreddit).sticky(number=2)
        except prawcore.exceptions.NotFound:  # Ignore if there is no sticky
            pass
        new_thread_mod.mod.sticky(state=True, bottom=bottom_sticky)
        if sticky_to_keep:
            sticky_to_keep.mod.sticky(state=True)

    if current_thread and current_thread_mod:
        # Update links to point to new thread
        links = {
            getattr(current_thread, link_type).strip("/"): (
                getattr(new_thread, link_type).strip("/"))
            for link_type in ["permalink", "shortlink"]}
        update_page_links(
            links=links,
            pages_to_update=thread_config.link_update_pages,
            reddit=reddit_mod,
            context=thread_config.context,
            uid=thread_config.uid + ".link_update_pages",
            description=thread_config.description,
            )

        # Add messages to new thread on old thread if enabled
        redirect_template = thread_config.new_thread_redirect_template
        redirect_message = redirect_template.strip().format(**template_vars)

        if thread_config.new_thread_redirect_op:
            current_thread.edit(
                redirect_message + "\n\n" + current_thread.selftext)
        if thread_config.new_thread_redirect_sticky:
            redirect_comment = current_thread_mod.reply(redirect_message)
            redirect_comment.mod.distinguish(sticky=True)

    # Update config accordingly
    dynamic_config.thread_id = new_thread.id


def sync_thread(
        thread_config: ThreadConfig,
        dynamic_config: DynamicThreadConfig,
        accounts: AccountsMap,
        ) -> None:
    """Sync a managed thread from its source."""
    if not dynamic_config.thread_id:
        raise SubManagerValueError(
            "Thread ID for must be specified for thread sync to work "
            f"for thread {thread_config!r}",
            message_post=f"Dynamic Config: {dynamic_config!r}")

    thread_target = FullEndpointConfig(
        context=thread_config.target_context,
        description=(
            f"{thread_config.description or thread_config.uid} Megathread"),
        endpoint_name=dynamic_config.thread_id,
        endpoint_type=EndpointType.THREAD,
        uid=thread_config.uid + ".target"
        )
    sync_pair = SyncPairConfig(
        description=thread_config.description,
        source=thread_config.source,
        targets={"megathread": thread_target},
        uid=thread_config.uid + ".sync_pair"
        )
    sync_one(
        sync_pair=sync_pair,
        dynamic_config=dynamic_config,
        accounts=accounts,
        )


def should_post_new_thread(
        thread_config: ThreadConfig,
        dynamic_config: DynamicThreadConfig,
        reddit: praw.reddit.Reddit) -> bool:
    """Determine if a new thread should be posted."""
    # Don't create a new thread if disabled, otherwise always create if no prev
    if not thread_config.new_thread_interval:
        return False
    if not dynamic_config.thread_id:
        return True

    # Process the interval and the current thread
    interval_unit, interval_n = process_raw_interval(
        thread_config.new_thread_interval)
    current_thread: praw.models.reddit.submission.Submission = (
        reddit.submission(id=dynamic_config.thread_id))

    # Get last post and current timestamp
    last_post_timestamp = datetime.datetime.fromtimestamp(
        current_thread.created_utc, tz=datetime.timezone.utc)
    current_datetime = datetime.datetime.now(datetime.timezone.utc)

    # If fixed unit interval, simply compare equality, otherwise compare delta
    if interval_n is None:
        previous_n: int = getattr(last_post_timestamp, interval_unit)
        current_n: int = getattr(current_datetime, interval_unit)
        interval_exceeded = not previous_n == current_n
    else:
        delta_kwargs: dict[str, int] = {
            f"{interval_unit}s": interval_n}
        relative_timedelta = dateutil.relativedelta.relativedelta(
            **delta_kwargs)  # type: ignore[arg-type]
        interval_exceeded = (
            current_datetime > (
                last_post_timestamp + relative_timedelta))

    return interval_exceeded


def manage_thread(
        thread_config: ThreadConfig,
        dynamic_config: DynamicThreadConfig,
        accounts: AccountsMap,
        ) -> None:
    """Manage the current thread, creating or updating it as necessary."""
    if not thread_config.enabled:
        return

    # Determine if its time to post a new thread
    post_new_thread = should_post_new_thread(
        thread_config=thread_config,
        dynamic_config=dynamic_config,
        reddit=accounts[thread_config.context.account])

    if post_new_thread:
        # If needed post a new thread
        print("Creating new thread for", thread_config.description,
              f"{thread_config.uid}")
        create_new_thread(thread_config, dynamic_config, accounts)
    else:
        # Otherwise, sync the current thread
        sync_thread(
            thread_config=thread_config,
            dynamic_config=dynamic_config,
            accounts=accounts,
            )


def manage_threads(
        static_config: StaticConfig,
        dynamic_config: DynamicConfig,
        accounts: AccountsMap,
        ) -> None:
    """Check and create/update all defined megathreads for a sub."""
    for thread_key, thread_config in (
            static_config.megathread.megathreads.items()):
        manage_thread(
            thread_config=thread_config,
            dynamic_config=dynamic_config.megathread[thread_key],
            accounts=accounts,
            )


# ----------------- Sync functionality -----------------

def parse_menu(
        source_text: str,
        menu_config: MenuConfig | None = None,
        ) -> MenuData:
    """Parse source Markdown text and render it into a strucured format."""
    if menu_config is None:
        menu_config = MenuConfig()

    menu_data: MenuData = []
    source_text = source_text.replace("\r\n", "\n")
    menu_sections = split_and_clean_text(
        source_text, menu_config.split)
    for menu_section in menu_sections:
        section_data: SectionData
        menu_subsections = split_and_clean_text(
            menu_section, menu_config.subsplit)
        if not menu_subsections:
            continue
        title_text = extract_text(
            menu_config.pattern_title, menu_subsections[0])
        if title_text is False:
            continue
        section_data = {"text": title_text}
        if len(menu_subsections) == 1:
            url_text = extract_text(
                menu_config.pattern_url, menu_subsections[0])
            if url_text is False:
                continue
            section_data["url"] = url_text
        else:
            children: ChildrenData = []
            for menu_child in menu_subsections[1:]:
                title_text = extract_text(
                    menu_config.pattern_subtitle, menu_child)
                url_text = extract_text(
                    menu_config.pattern_url, menu_child)
                if title_text is not False and url_text is not False:
                    children.append(
                        {"text": title_text, "url": url_text})
            section_data["children"] = children
        menu_data.append(section_data)
    return menu_data


def process_endpoint_text(
        content: str,
        config: PatternConfig,
        replace_text: str | None = None,
        ) -> str | Literal[False]:
    """Perform the desired find-replace for a specific sync endpoint."""
    match_obj = search_startend(
        content,
        config.pattern,
        config.pattern_start,
        config.pattern_end,
        )
    if match_obj is not False:
        if not match_obj:
            return False
        output_text = match_obj.group()
        if replace_text is not None:
            output_text = content.replace(output_text, replace_text)
        return output_text

    return content if replace_text is None else replace_text


def process_source_endpoint(
        source_config: FullEndpointConfig,
        source_obj: SyncEndpoint,
        dynamic_config: DynamicSyncConfig,
        ) -> str | MenuData | Literal[False]:
    """Get and preprocess the text from a source if its out of date."""
    # If source has revision date, check it and skip if unchanged
    if isinstance(source_obj, RevisionDateCheckable):
        source_timestamp = source_obj.revision_date
        source_updated = (
            source_timestamp > dynamic_config.source_timestamp)
        if not source_updated:
            return False
        dynamic_config.source_timestamp = source_timestamp

    source_content = source_obj.content
    if isinstance(source_content, str):
        source_content_processed = process_endpoint_text(
            source_content, source_config)
        if source_content_processed is False:
            print("Skipping sync pattern not found in source "
                  f"{source_obj.config.description} {source_obj.config.uid}")
            return False
        source_content_processed = replace_patterns(
            source_content_processed, source_config.replace_patterns)
        return source_content_processed

    return source_content


def process_target_endpoint(
        target_config: FullEndpointConfig,
        target_obj: SyncEndpoint,
        source_content: str | MenuData,
        menu_config: MenuConfig | None = None,
        ) -> str | MenuData | Literal[False]:
    """Handle text conversions and deployment onto a sync target."""
    if isinstance(source_content, str):
        source_content = replace_patterns(
            source_content, target_config.replace_patterns)

    target_content = target_obj.content
    if (isinstance(target_obj, MenuSyncEndpoint)
            and isinstance(source_content, str)):
        target_content = parse_menu(
            source_text=source_content,
            menu_config=menu_config,
            )
    elif isinstance(source_content, str) and isinstance(target_content, str):
        target_content_processed = process_endpoint_text(
            target_content, target_config, replace_text=source_content)
        if target_content_processed is False:
            print("Skipping sync pattern not found in target "
                  f"{target_obj.config.description} {target_obj.config.uid}")
            return False
        return target_content_processed

    return target_content


def sync_one(
        sync_pair: SyncPairConfig,
        dynamic_config: DynamicSyncConfig,
        accounts: AccountsMap,
        ) -> None:
    """Sync one specific pair of sources and targets."""
    if not (sync_pair.enabled and sync_pair.source.enabled):
        return

    source_obj = create_sync_endpoint_from_config(
        config=sync_pair.source,
        reddit=accounts[sync_pair.source.context.account])
    source_content = process_source_endpoint(
        sync_pair.source, source_obj, dynamic_config)
    if source_content is False:
        return

    for target_config in sync_pair.targets.values():
        if not target_config.enabled:
            continue

        target_obj = create_sync_endpoint_from_config(
            config=target_config,
            reddit=accounts[target_config.context.account])
        target_content = process_target_endpoint(
            target_config=target_config,
            target_obj=target_obj,
            source_content=source_content,
            menu_config=sync_pair.source.menu_config,
            )
        if target_content is False:
            continue

        target_obj.edit(
            target_content,
            reason=(f"Auto-sync {sync_pair.description or sync_pair.uid} "
                    f"from {target_obj.config.endpoint_name}"),
            )


def sync_all(static_config: StaticConfig,
             dynamic_config: DynamicConfig,
             accounts: AccountsMap,
             ) -> None:
    """Sync all pairs of sources/targets (pages,threads, sections) on a sub."""
    for sync_pair_id, sync_pair in static_config.sync.pairs.items():
        sync_one(
            sync_pair=sync_pair,
            dynamic_config=dynamic_config.sync[sync_pair_id],
            accounts=accounts,
            )


# ----------------- Setup and run -----------------

# ---- Setup routines ----

def handle_refresh_tokens(
        accounts_config: AccountsConfig,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        ) -> AccountsConfigProcessed:
    """Set up each account with the appropriate refresh tokens."""
    config_path_refresh = Path(config_path_refresh)
    accounts_config_processed: AccountsConfigProcessed = (
        accounts_config)  # type: ignore[assignment]
    accounts_config_processed = copy.deepcopy(accounts_config_processed)

    for account_key, account_kwargs in accounts_config.items():
        refresh_token = account_kwargs.get("refresh_token", None)
        if refresh_token:
            del accounts_config_processed[account_key]["refresh_token"]
            # Initialize refresh token file
            token_path: Path = config_path_refresh.with_name(
                config_path_refresh.name.format(key=account_key))
            token_path.parent.mkdir(parents=True, exist_ok=True)
            if not token_path.exists():
                with open(token_path, "w",
                          encoding="utf-8", newline="\n") as token_file:
                    token_file.write(refresh_token)

            # Set up refresh token manager
            token_manager = praw.util.token_manager.FileTokenManager(
                token_path)  # type: ignore[no-untyped-call]
            accounts_config_processed[account_key]["token_manager"] = (
                token_manager)

    return accounts_config_processed


def perform_test_request(
        reddit: praw.reddit.Reddit,
        account_key: str,
        raise_error: bool = True,
        ) -> bool:
    """Perform a test Reddit request based on the scope to confirm access."""
    scopes: set[str] = reddit.auth.scopes()
    if not scopes:
        if not raise_error:
            return False
        raise NoAuthorizedScopesError(
            account_key=account_key,
            message_pre="The OAUTH token has no authorized scope ({scopes!r})",
            )

    try:
        scope_check = ""
        testable_scopes = {"*", "identity", "read", "wikiread"}
        warning_message = (f"Error finding {{test_item}} testing {{scope}} "
                           f"with account {account_key!r} ({{error}})")
        if "*" in scopes or "identity" in scopes:
            scope_check = "identity"
            reddit.user.me()
        elif "read" in scopes:
            scope_check = "read"
            test_sub = "all"
            try:
                list(reddit.subreddit(test_sub).hot(limit=1))[0].id
            except PRAW_NOTFOUND_ERRORS as error:
                warning_message = warning_message.format(
                    scope=scope_check,
                    test_item=f"sub 'r/{test_sub}'",
                    error=format_error(error),
                    )
                warnings.warn(
                    warning_message, TestPageNotFoundWarning, stacklevel=2)
        elif "wikiread" in scopes:
            scope_check = "wiki read"
            test_sub = "help"
            test_page = "index"
            try:
                reddit.subreddit(test_sub).wiki[test_page].content_md
            except PRAW_NOTFOUND_ERRORS as error:
                warning_message = warning_message.format(
                    scope=scope_check,
                    test_item=f"sub 'r/{test_sub}', wiki page {test_page!r}",
                    error=format_error(error),
                    )
                warnings.warn(
                    warning_message, TestPageNotFoundWarning, stacklevel=2)
        else:
            warning_message = (
                f"Account {account_key!r} scopes ({scopes!r}) did not include"
                f"any that could be tested for access ({testable_scopes!r})")
            warnings.warn(
                warning_message, NoTestableScopesWarning, stacklevel=2)

    except PRAW_AUTHORIZATION_ERRORS as error:
        if not raise_error:
            return False
        raise AccountCheckAuthError(
            account_key=account_key,
            message_pre=f"Authorization error when testing {scope_check}",
            message_post=error,
            ) from error
    except PRAW_REDDIT_ERRORS as error:
        if not raise_error:
            return False
        raise AccountCheckError(
            account_key=account_key,
            message_pre=(f"Non-authorization error when testing {scope_check} "
                         "(maybe Reddit's having problems?)"),
            message_post=error,
            ) from error

    return True


def validate_account(
        reddit: praw.reddit.Reddit,
        account_key: str,
        raise_error: bool = True,
        ) -> bool:
    """Check if the Reddit account associated with the object is authorized."""
    read_only = reddit.read_only
    if read_only or read_only is None:
        if not raise_error:
            return False
        raise RedditReadOnlyError(
            account_key=account_key,
            message_pre="Reddit instance is read-only",
            message_post="Account authorization failed; check credentials.",
            )

    test_succeeded = perform_test_request(
        reddit=reddit, account_key=account_key, raise_error=raise_error)
    return test_succeeded


def validate_accounts(
        accounts: AccountsMap,
        raise_error: bool = True,
        verbose: bool = False,
        ) -> dict[str, bool]:
    """Validate that the passed accounts are authenticated and work."""
    vprint = VerbosePrinter(verbose)

    accounts_valid = {}
    for account_key, reddit in accounts.items():
        vprint(f"Validating account {account_key!r}")
        account_valid = validate_account(
            reddit, account_key=account_key, raise_error=raise_error)
        accounts_valid[account_key] = account_valid
    return accounts_valid


def setup_accounts(
        accounts_config: AccountsConfig,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        verbose: bool = False,
        ) -> AccountsMap:
    """Set up the PRAW Reddit objects for each account in the config."""
    vprint = VerbosePrinter(verbose)

    vprint("Processing refresh tokens at path "
           f"{Path(config_path_refresh).as_posix()!r}")
    accounts_config_processed = handle_refresh_tokens(
        accounts_config, config_path_refresh=config_path_refresh)

    accounts = {}
    for account_key, account_kwargs in accounts_config_processed.items():
        vprint(f"Setting up account {account_key!r}")
        try:
            reddit = praw.reddit.Reddit(
                user_agent=USER_AGENT,
                praw8_raise_exception_on_me=True,
                **account_kwargs)
        except PRAW_ALL_ERRORS as error:
            raise AccountConfigError(
                account_key=account_key, message_post=error) from error
        reddit.validate_on_submit = True
        accounts[account_key] = reddit
    return accounts


def setup_config(
        config_paths: ConfigPaths | None = None,
        verbose: bool = False,
        ) -> tuple[StaticConfig, DynamicConfig]:
    """Load the config and set up the accounts mapping."""
    vprint = VerbosePrinter(verbose)
    config_paths = ConfigPaths() if config_paths is None else config_paths

    # Load the configuration
    vprint("Loading static configuration at path "
           f"{config_paths.static.as_posix()!r}")
    static_config = load_static_config(config_paths.static)
    vprint("Loading dynamic configuration at path "
           f"{config_paths.dynamic.as_posix()!r}")
    dynamic_config = load_dynamic_config(
        static_config=static_config, config_path=config_paths.dynamic)

    return static_config, dynamic_config


def validate_config_offline(
        static_config: StaticConfig,
        config_paths: ConfigPaths | None = None,
        error_default: bool = True,
        raise_error: bool = True,
        verbose: bool = False
        ) -> bool:
    """Validate config locally without connecting to Reddit."""
    vprint = VerbosePrinter(verbose)
    config_paths = ConfigPaths() if config_paths is None else config_paths

    # If default config was generated and is unmodified, raise an error
    if error_default:
        vprint("Checking that config has been set up")
        if static_config.accounts == EXAMPLE_ACCOUNTS:
            if not raise_error:
                return False
            raise ConfigDefaultError(config_paths.static)

    return True


def validate_endpoint(
        config: EndpointTypeConfig,
        accounts: AccountsMap,
        check_editable: bool | None = None,
        raise_error: bool = True,
        ) -> bool:
    """Validate that the sync endpoint points to a valid Reddit object."""
    if check_editable is None:
        check_editable = "target" in config.uid
    reddit = accounts[config.context.account]
    details_urls = [
        "https://www.reddit.com/dev/api/oauth",
        "https://praw.readthedocs.io/en/stable/tutorials/refresh_token.html",
        ]
    endpoint_valid = False

    try:
        endpoint = create_sync_endpoint_from_config(
            config=config, reddit=reddit, validate=False)
        endpoint_valid = endpoint.validate(raise_error=raise_error)
        if endpoint_valid and check_editable:
            endpoint_valid = bool(endpoint.check_is_editable(
                raise_error=raise_error))
    except prawcore.exceptions.InsufficientScope as error:
        if not raise_error:
            return False
        urls_formatted = " or ".join([f"<{url}>" for url in details_urls])
        raise InsufficientScopeError(
            config,
            message_pre=(
                f"Could not {'edit' if endpoint_valid else 'retrieve'} "
                f"{config.endpoint_type!s} due to the OAUTH scopes "
                f"{reddit.auth.scopes()!r} "
                f"of the refresh token for account {config.context.account!r} "
                "not including the scope required for this operation "
                f"(see {urls_formatted!s} for details)"),
            message_post=error,
            ) from error

    return endpoint_valid


def get_all_endpoints(
        static_config: StaticConfig,
        include_disabled: bool = False,
        ) -> list[FullEndpointConfig]:
    """Get all sync endpoints defined in the current static config."""
    all_endpoints: list[FullEndpointConfig] = []
    if include_disabled or static_config.sync.enabled:
        for sync_pair in static_config.sync.pairs.values():
            if include_disabled or sync_pair.enabled:
                all_endpoints.append(sync_pair.source)
                all_endpoints += list(sync_pair.targets.values())
    if include_disabled or static_config.megathread.enabled:
        for thread in static_config.megathread.megathreads.values():
            if include_disabled or thread.enabled:
                all_endpoints.append(thread.source)
    if not include_disabled:
        all_endpoints = [
            endpoint for endpoint in all_endpoints if endpoint.enabled]
    return all_endpoints


def validate_endpoints(
        static_config: StaticConfig,
        accounts: AccountsMap,
        include_disabled: bool = False,
        raise_error: bool = True,
        verbose: bool = False,
        ) -> dict[str, bool]:
    """Validate all the endpoints defined in the config."""
    vprint = VerbosePrinter(verbose)
    vprint("Extracting all endpoints from config")
    all_endpoints = get_all_endpoints(
        static_config=static_config, include_disabled=include_disabled)

    endpoints_valid = {}
    for endpoint in all_endpoints:
        vprint(f"Validating endpoint {endpoint.uid!r}")
        endpoint_valid = validate_endpoint(
            config=endpoint, accounts=accounts, raise_error=raise_error)
        endpoints_valid[endpoint.uid] = endpoint_valid

    return endpoints_valid


def validate_config(
        config_paths: ConfigPaths | None = None,
        offline: bool = False,
        raise_error: bool = True,
        verbose: bool = False,
        ) -> bool:
    """Check if the config is valid."""
    vprint = FancyPrinter(enable=verbose)
    config_paths = ConfigPaths() if config_paths is None else config_paths

    try:
        vprint("Checking offline config", level=1)
        static_config, __ = setup_config(
            config_paths=config_paths,
            verbose=verbose,
            )
        validate_config_offline(
            static_config=static_config,
            config_paths=config_paths,
            raise_error=True,
            verbose=verbose,
            )
        if not offline:
            vprint("Checking accounts", level=1)
            accounts = setup_accounts(
                static_config.accounts,
                config_path_refresh=config_paths.refresh,
                verbose=verbose,
                )
            validate_accounts(
                accounts=accounts,
                raise_error=True,
                verbose=verbose,
                )

            vprint("Checking endpoints", level=1)
            validate_endpoints(
                static_config=static_config,
                accounts=accounts,
                raise_error=True,
                verbose=verbose,
                )

    except SubManagerUserError:
        if not raise_error:
            return False
        raise
    else:
        return True


def run_initial_setup(
        config_paths: ConfigPaths | None = None,
        validate: bool = True,
        ) -> tuple[StaticConfig, AccountsMap]:
    """Run initial run-time setup for each time the application is started."""
    config_paths = ConfigPaths() if config_paths is None else config_paths
    if validate:
        validate_config(
            config_paths=config_paths,
            offline=False,
            raise_error=True,
            verbose=True,
            )
    static_config, __ = setup_config(config_paths=config_paths)
    accounts = setup_accounts(
        static_config.accounts, config_path_refresh=config_paths.refresh)
    return static_config, accounts


# ---- High level command code ----

def run_generate_config(
        config_paths: ConfigPaths | None = None,
        force: bool = False,
        exist_ok: bool = False,
        ) -> None:
    """Generate the various config files for sub manager."""
    config_paths = ConfigPaths() if config_paths is None else config_paths
    config_exists = generate_static_config(
        config_path=config_paths.static, force=force, exist_ok=exist_ok)

    message = f"Config {{action}} at {config_paths.static.as_posix()!r}"
    if not config_exists:
        action = "generated"
    elif force:
        action = "overwritten"
    else:
        action = "already exists"
    print(message.format(action=action))


def run_validate_config(
        config_paths: ConfigPaths | None = None,
        offline: bool = False,
        ) -> None:
    """Check if the config is valid, raising an error if it is not."""
    wprint = FancyPrinter()
    wprint("Validating configuration in "
           f"{'offline' if offline else 'online'} mode", level=2)
    try:
        validate_config(
            config_paths=config_paths,
            offline=offline,
            raise_error=True,
            verbose=True,
            )
    except SubManagerUserError:
        wprint("Config validation FAILED", level=2)
        raise
    except Exception:
        wprint("Unexpected error occured during config validation:", level=2)
        raise
    else:
        wprint("Config validation SUCCEEDED", level=2)


# ---- Core run code ----

def run_manage_once(
        static_config: StaticConfig,
        accounts: AccountsMap,
        config_path_dynamic: PathLikeStr = CONFIG_PATH_DYNAMIC,
        ) -> None:
    """Run the manage loop once, without validation checks."""
    # Load config and set up session
    print("Running Sub Manager")
    dynamic_config = load_dynamic_config(
        static_config=static_config, config_path=config_path_dynamic)
    dynamic_config_active = dynamic_config.copy(deep=True)

    # Run the core manager tasks
    if static_config.sync.enabled:
        sync_all(static_config, dynamic_config_active, accounts)
    if static_config.megathread.enabled:
        manage_threads(static_config, dynamic_config_active, accounts)

    # Write out the dynamic config if it changed
    if dynamic_config_active != dynamic_config:
        write_config(dynamic_config_active, config_path=config_path_dynamic)
    print("Sub Manager run complete")


def run_manage(
        config_paths: ConfigPaths | None = None,
        skip_validate: bool = False,
        ) -> None:
    """Load the config file and run the thread manager."""
    config_paths = ConfigPaths() if config_paths is None else config_paths
    static_config, accounts = run_initial_setup(
        config_paths, validate=not skip_validate)
    run_manage_once(
        static_config=static_config,
        accounts=accounts,
        config_path_dynamic=config_paths.dynamic,
        )


def start_manage(
        config_paths: ConfigPaths | None = None,
        repeat_interval_s: float | None = None,
        skip_validate: bool = False,
        ) -> None:
    """Run the mainloop of sub-manager, performing each task in sequance."""
    # Load config and set up session
    print("Starting Sub Manager")
    config_paths = ConfigPaths() if config_paths is None else config_paths
    static_config, accounts = run_initial_setup(
        config_paths, validate=not skip_validate)

    if repeat_interval_s is None:
        repeat_interval_s = static_config.repeat_interval_s
    while True:
        run_manage_once(
            static_config=static_config,
            accounts=accounts,
            config_path_dynamic=config_paths.dynamic,
            )
        try:
            time_left_s = repeat_interval_s
            while True:
                time_to_sleep_s = min((time_left_s, 1))
                time.sleep(time_to_sleep_s)
                time_left_s -= 1
                if time_left_s <= 0:
                    break
        except KeyboardInterrupt:
            print("Recieved keyboard interrupt; exiting")
            break


# ---- CLI ----

def get_version_str() -> str:
    """Get a pretty-printed string of the application's version."""
    return f"Megathread Manager version {__version__}"


def create_arg_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser_main = argparse.ArgumentParser(
        description="Generate, post, update and pin a Reddit megathread",
        argument_default=argparse.SUPPRESS)
    subparsers = parser_main.add_subparsers(
        description="Subcommand to execute")

    # Top-level arguments
    parser_main.add_argument(
        "--version",
        action="store_true",
        help="Print the version number and exit",
        )
    parser_main.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Print full debug output instead of just user-friendly text",
        )
    parser_main.add_argument(
        "--config-path",
        dest="config_path_static",
        help="The path to a custom static (user) config file to use",
        )
    parser_main.add_argument(
        "--dynamic-config-path",
        dest="config_path_dynamic",
        help="The path to a custom dynamic (runtime) config file to use",
        )
    parser_main.add_argument(
        "--refresh-config-path",
        dest="config_path_refresh",
        help="The path to a custom (set of) refresh token files to use",
        )

    # Generate the config file
    generate_desc = "Generate the bot's config files"
    parser_generate = subparsers.add_parser(
        "generate-config",
        description=generate_desc,
        help=generate_desc,
        argument_default=argparse.SUPPRESS,
        )
    parser_generate.set_defaults(func=run_generate_config)
    parser_generate.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the existing static config with the default example",
        )
    parser_generate.add_argument(
        "--exist-ok",
        action="store_true",
        help="Don't raise an error/warning if the config file already exists",
        )

    # Validate the config file
    validate_desc = "Validate the bot's config files"
    parser_validate = subparsers.add_parser(
        "validate-config",
        description=validate_desc,
        help=validate_desc,
        argument_default=argparse.SUPPRESS,
        )
    parser_validate.set_defaults(func=run_validate_config)
    parser_validate.add_argument(
        "--offline",
        action="store_true",
        help="Just validate the config locally, don't call out to Reddit",
        )

    # Run the bot once
    run_desc = "Run the bot through one cycle and exit"
    parser_run = subparsers.add_parser(
        "run",
        description=run_desc,
        help=run_desc,
        argument_default=argparse.SUPPRESS,
        )
    parser_run.set_defaults(func=run_manage)
    parser_run.add_argument(
        "--skip-validate",
        action="store_true",
        help="Don't validate the config against Reddit prior to executing it",
        )

    # Start the bot running
    start_desc = "Start the bot running continously until stopped or errored"
    parser_start = subparsers.add_parser(
        "start",
        description=start_desc,
        help=start_desc,
        argument_default=argparse.SUPPRESS,
        )
    parser_start.set_defaults(func=start_manage)
    parser_start.add_argument(
        "--repeat-interval-s",
        type=float,
        metavar="N",
        help=("Run every N seconds, or the value from the config file "
              "variable repeat_interval_s if N isn't specified"),
        )
    parser_start.add_argument(
        "--skip-validate",
        action="store_true",
        help="Don't validate the config against Reddit prior to executing it",
        )

    return parser_main


def run_toplevel_function(
        func: Callable[..., None],
        config_path_static: PathLikeStr = CONFIG_PATH_STATIC,
        config_path_dynamic: PathLikeStr = CONFIG_PATH_DYNAMIC,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        **kwargs: Any,
        ) -> None:
    """Dispatch to the top-level function, converting paths to objs."""
    config_paths = ConfigPaths(
        static=Path(config_path_static),
        dynamic=Path(config_path_dynamic),
        refresh=Path(config_path_refresh),
        )
    func(config_paths=config_paths, **kwargs)


def handle_parsed_args(parsed_args: argparse.Namespace) -> None:
    """Dispatch to the specified command based on the passed args."""
    # Print version and exit if --version passed
    version: bool = getattr(parsed_args, "version", None)
    if version:
        print(get_version_str())
        return

    # Execute desired subcommand function if passed, otherwise print help
    try:
        parsed_args.func
    except AttributeError:  # If function is not specified
        create_arg_parser().print_usage()
    else:
        run_toplevel_function(**vars(parsed_args))


def main(sys_argv: list[str] | None = None) -> None:
    """Run the main function for the Megathread Manager CLI and dispatch."""
    parser_main = create_arg_parser()
    parsed_args = parser_main.parse_args(sys_argv)
    debug: bool = vars(parsed_args).pop("debug")
    try:
        handle_parsed_args(parsed_args)
    except SubManagerUserError as error:
        if debug:
            raise
        print(f"\n{'v' * 70}\n{format_error(error)}\n{'^' * 70}\n",
              file=sys.stderr)
        sys.exit(EXIT_CODE_USER_ERROR)


if __name__ == "__main__":
    main()
