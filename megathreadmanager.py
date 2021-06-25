#!/usr/bin/env python3
"""Generate, pin and update a regular megathread for a subreddit."""

# Future imports
from __future__ import annotations

# Standard library imports
import abc
import argparse
import copy
import datetime
import enum
import json
import os
from pathlib import Path
import re
import time
from typing import (
    Any,
    Callable,  # Added to collections.abc in Python 3.9
    Dict,  # Not needed in Python 3.9
    Generic,
    List,  # Not needed in Python 3.9
    Mapping,  # Added to collections.abc in Python 3.9
    MutableMapping,  # Added to collections.abc in Python 3.9
    NoReturn,
    TYPE_CHECKING,
    TypeVar,
    Union,  # Not needed in Python 3.9
    )
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    Literal,  # Added to typing in Python 3.8
    )

# Third party imports
import dateutil.relativedelta
import praw
import praw.util.token_manager
import prawcore.exceptions
import pydantic
import toml


# ----------------- Constants -----------------

__version__: Final = "0.6.0dev0"

# General constants
CONFIG_DIRECTORY: Final = Path("~/.config/megathread-manager").expanduser()
CONFIG_PATH_STATIC: Final = CONFIG_DIRECTORY / "config.toml"
CONFIG_PATH_DYNAMIC: Final = CONFIG_DIRECTORY / "config_dynamic.json"
CONFIG_PATH_REFRESH: Final = CONFIG_DIRECTORY / "refresh_token_{key}.txt"
USER_AGENT: Final = f"praw:megathreadmanager:v{__version__} (by u/CAM-Gerlach)"


# Enum values
@enum.unique
class EndpointType(enum.Enum):
    """Reprisent the type of sync endpoint on Reddit."""

    def __repr__(self) -> str:
        """Convert enum value to repr."""
        return str(self.value)

    def __str__(self) -> str:
        """Convert enum value to string."""
        return str(self.value)

    MENU = "MENU"
    THREAD = "THREAD"
    WIDGET = "WIDGET"
    WIKI_PAGE = "WIKI_PAGE"


# Type aliases
if TYPE_CHECKING:
    PathLikeStr = Union['os.PathLike[str]', str]
else:
    PathLikeStr = Union[os.PathLike, str]

EndpointTypesStr = Literal["MENU", "THREAD", "WIDGET", "WIKI_PAGE"]

ChildrenData = List[MutableMapping[str, str]]
SectionData = MutableMapping[str, Union[str, ChildrenData]]
MenuData = List[SectionData]

AccountConfig = Mapping[str, str]
AccountsConfig = Mapping[str, AccountConfig]
AccountsMap = Mapping[str, praw.Reddit]
ConfigDict = Mapping[str, Any]
ConfigDictDynamic = MutableMapping[str, MutableMapping[str, Any]]


# Config constants
DEFAULT_REDIRECT_TEMPLATE: Final = """
This thread is no longer being updated, and has been replaced by:

# [{post_title}]({thread_url})
"""


# ----------------- Config classes -----------------

class ThreadIDStr(pydantic.ConstrainedStr):
    """Pydantic type class for a thread ID of exactly 6 characters."""

    max_length = 6
    min_length = 6


class MenuConfig(pydantic.BaseModel):
    """Configuration to parse the menu data from Markdown text."""

    split: str = "\n\n"
    subsplit: str = "\n"
    pattern_title: str = r"\[([^\n\]]*)\]\("
    pattern_url: str = r"\]\(([^\s\)]*)[\s\)]"
    pattern_subtitle: str = r"\[([^\n\]]*)\]\("


class PatternConfig(pydantic.BaseModel):
    """Configuration for the section pattern-matching."""

    pattern: Union[str, Literal[False]] = False
    pattern_end: str = " End"
    pattern_start: str = " Start"


class ContextConfig(pydantic.BaseModel):
    """Local context configuration for the bot."""

    account: str
    subreddit: str


class EndpointConfig(pydantic.BaseModel):
    """Config params specific to sync endpoint setup."""

    context: ContextConfig
    endpoint_name: str
    endpoint_type: EndpointType = EndpointType.WIKI_PAGE
    description: str = ""

    @pydantic.validator("description")
    def description_fill(  # pylint: disable = no-self-use, no-self-argument
            cls, value: str, values: dict[str, Any]) -> str:
        """Fill the description from the endpoint name, if not provided."""
        if not value:
            endpoint_name: str = values["endpoint_name"]
            return endpoint_name.replace("_", " ").title()
        return value


class FullEndpointConfig(EndpointConfig, PatternConfig):
    """Config params for a sync source/target endpoint."""

    enabled: bool = True
    menu_config: MenuConfig = MenuConfig()
    replace_patterns: Mapping[str, str] = {}


class SyncPairConfig(pydantic.BaseModel):
    """Configuration object for a sync pair of a source and target(s)."""

    description: str = ""
    enabled: bool = True
    source: FullEndpointConfig
    targets: Mapping[str, FullEndpointConfig]


class SyncConfig(pydantic.BaseModel):
    """Top-level configuration for the thread management module."""

    enabled: bool = True
    pairs: Mapping[str, SyncPairConfig] = {}


class InitialThreadConfig(pydantic.BaseModel):
    """Initial configuration of a managed thread."""

    thread_id: Union[Literal[False], ThreadIDStr] = False
    thread_number: pydantic.NonNegativeInt = 0


class ThreadConfig(pydantic.BaseModel):
    """Configuration for a managed thread item."""

    context: ContextConfig
    description: str = ""
    enabled: bool = True
    initial: InitialThreadConfig = InitialThreadConfig()
    link_update_pages: List[str] = []
    new_thread_interval: str = "month"
    new_thread_redirect_op: bool = False
    new_thread_redirect_sticky: bool = False
    new_thread_redirect_template: str = DEFAULT_REDIRECT_TEMPLATE
    pin_thread: Union[Literal["top"], Literal["bottom"], bool] = "top"
    post_title_template: str = "{subreddit} Megathread (#{thread_number})"
    source: FullEndpointConfig
    target_context: ContextConfig


class ThreadsConfig(pydantic.BaseModel):
    """Top-level configuration for the thread management module."""

    enabled: bool = True
    megathreads: Mapping[str, ThreadConfig] = {}


class StaticConfig(pydantic.BaseModel):
    """Model reprisenting the bot's static configuration."""

    repeat_interval_s: float = 60
    accounts: AccountsConfig
    context_default: ContextConfig
    megathread: ThreadsConfig = ThreadsConfig()
    sync: SyncConfig = SyncConfig()


class DynamicSyncConfig(pydantic.BaseModel):
    """Dynamically-updated configuration for sync pairs."""

    source_timestamp: pydantic.NonNegativeFloat = 0


class DynamicThreadConfig(DynamicSyncConfig, InitialThreadConfig):
    """Dynamically-updated configuration for managed threads."""


class DynamicConfig(pydantic.BaseModel):
    """Model reprisenting the current dynamic configuration."""

    megathread: Dict[str, DynamicThreadConfig] = {}
    sync: Dict[str, DynamicSyncConfig] = {}


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
    )

EXAMPLE_TARGET: Final = FullEndpointConfig(
    context=EXAMPLE_CONTEXT,
    description="Example sync target",
    endpoint_name="EXAMPLE_TARGET_NAME",
    )

EXAMPLE_SYNC_PAIR: Final = SyncPairConfig(
    description="Example sync pair",
    enabled=False,
    source=EXAMPLE_SOURCE,
    targets={"EXAMPLE_TARGET": EXAMPLE_TARGET},
    )


EXAMPLE_THREAD: Final = ThreadConfig(
    context=EXAMPLE_CONTEXT,
    description="Example managed thread",
    enabled=False,
    source=EXAMPLE_SOURCE,
    target_context=EXAMPLE_CONTEXT,
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
                "source": {"context"},
                "target_context": ...,
                },
            },
        },
    "sync": {
        "pairs": {
            "EXAMPLE_SYNC_PAIR": {
                "source": {"context"},
                "target": {"context"},
                },
            },
        },
    }


# ----------------- Helper functions -----------------

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


def extract_text(pattern: str, source_text: str) -> str | Literal[False]:
    """Match the given pattern and extract the matched text as a string."""
    match = re.search(pattern, source_text)
    if not match:
        return False
    match_text = match.groups()[0] if match.groups() else match.group()
    return match_text


def process_raw_interval(raw_interval: str) -> tuple[str, int | None]:
    """Convert a time interval expressed as a string into a standard form."""
    interval_split = raw_interval.split()
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


KeyType = TypeVar("KeyType")


def update_dict_recursive(
        base: MutableMapping[KeyType, Any],
        update: MutableMapping[KeyType, Any],
        inplace: bool | None = None,
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


# ----------------- Helper classes -----------------

class ConfigError(RuntimeError):
    """Raised when there is a problem with the Sub Manager configuration."""


class ConfigNotFoundError(ConfigError):
    """Raised when the Sub Manager configuration file is not found."""


F = TypeVar('F', bound=Callable[..., Any])  # pylint: disable=invalid-name


class copy_signature(Generic[F]):  # pylint: disable=invalid-name
    """Decorator to copy the signature from another function."""

    def __init__(self, target: F) -> None:  # pylint: disable=unused-argument
        ...

    def __call__(self, wrapped: Callable[..., Any]) -> F:
        """Call the function/method."""


class SyncEndpoint(metaclass=abc.ABCMeta):
    """Abstraction of a source or target for a Reddit sync action."""

    @abc.abstractmethod
    def __init__(
            self,
            endpoint_name: str,
            reddit: praw.Reddit,
            subreddit: str,
            description: str | None = None,
            ) -> None:
        self.name = endpoint_name
        self._reddit = reddit
        self._subreddit = self._reddit.subreddit(subreddit)
        self.description = endpoint_name if not description else description

    @property
    @abc.abstractmethod
    def content(self) -> str | MenuData:
        """Get the current content of the sync endpoint."""

    @abc.abstractmethod
    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the sync endpoint with the given content."""

    @property
    @abc.abstractmethod
    def revision_date(self) -> int | NoReturn:
        """Get the date the sync endpoint was last updated, if supported."""


class MenuSyncEndpoint(SyncEndpoint):
    """Sync endpoint reprisenting a New Reddit top bar menu widget."""

    @copy_signature(SyncEndpoint.__init__)
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if not self.name:
            self.name = "menu"
        for widget in self._subreddit.widgets.topbar:
            if widget.kind == self.name:
                self._object = widget
                break
        else:
            print("Menu widget not found; assuming its first in the topbar")
            self._object = self._subreddit.widgets.topbar[0]

    @property
    def content(self) -> MenuData:
        """Get the current structured data in the menu widget."""
        menu_data: MenuData = self._object.data
        return menu_data

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the menu with the given structured data."""
        self._object.mod.update(data=new_content)

    @property
    def revision_date(self) -> NoReturn:
        """Get the date the endpoint was updated; not supported for menus."""
        raise NotImplementedError


class ThreadSyncEndpoint(SyncEndpoint):
    """Sync endpoint reprisenting a Reddit thread (selfpost submission)."""

    @copy_signature(SyncEndpoint.__init__)
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._object = self._reddit.submission(id=self.name)

    @property
    def content(self) -> str:
        """Get the current submission's selftext."""
        submission_text: str = self._object.selftext
        assert isinstance(submission_text, str)
        return submission_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the thread's text to be that passed."""
        self._object.edit(new_content)

    @property
    def revision_date(self) -> int:
        """Get the date the thread was last edited."""
        edited_date: int | Literal[False] = self._object.edited
        if not edited_date:
            edited_date = self._object.created_utc
        assert isinstance(edited_date, int)
        return edited_date


class WidgetSyncEndpoint(SyncEndpoint):
    """Sync endpoint reprisenting a New Reddit sidebar text content widget."""

    @copy_signature(SyncEndpoint.__init__)
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        for widget in self._subreddit.widgets.sidebar:
            if widget.shortName == self.name:
                self._object = widget
                break
        else:
            raise ValueError(
                f"Widget {self.name} missing for endpoint {self.description}")

    @property
    def content(self) -> str:
        """Get the current text content of the sidebar widget."""
        widget_text: str = self._object.text
        assert isinstance(widget_text, str)
        return widget_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the sidebar widget with the given text content."""
        self._object.mod.update(text=new_content)

    @property
    def revision_date(self) -> NoReturn:
        """Get the date the endpoint was updated; not supported for widgets."""
        raise NotImplementedError


class WikiSyncEndpoint(SyncEndpoint):
    """Sync endpoint reprisenting a Reddit wiki page."""

    @copy_signature(SyncEndpoint.__init__)
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._object = self._subreddit.wiki[self.name]

    @property
    def content(self) -> str:
        """Get the current text content of the wiki page."""
        wiki_text: str = self._object.content_md
        assert isinstance(wiki_text, str)
        return wiki_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the wiki page with the given text."""
        self._object.edit(new_content, reason=reason)

    @property
    def revision_date(self) -> int:
        """Get the date the wiki page was last updated."""
        revision_timestamp: int = self._object.revision_date
        assert isinstance(revision_timestamp, int)
        return revision_timestamp


SYNC_ENDPOINT_TYPES: Final[Mapping[EndpointType, type[SyncEndpoint]]] = {
    EndpointType.MENU: MenuSyncEndpoint,
    EndpointType.THREAD: ThreadSyncEndpoint,
    EndpointType.WIDGET: WidgetSyncEndpoint,
    EndpointType.WIKI_PAGE: WikiSyncEndpoint,
    }


def create_sync_endpoint_from_config(
        config: EndpointConfig, reddit: praw.Reddit) -> SyncEndpoint:
    """Create a new sync endpoint given a particular config and Reddit obj."""
    sync_endpoint = SYNC_ENDPOINT_TYPES[config.endpoint_type](
        endpoint_name=config.endpoint_name,
        reddit=reddit,
        subreddit=config.context.subreddit,
        description=config.description,
        )
    return sync_endpoint


# ----------------- Config functions -----------------

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
        raise ConfigError("Format of config file not in {JSON, TOML}")
    return serialized_config


def write_config(
        config: ConfigDict | pydantic.BaseModel,
        config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
        ) -> str:
    """Write the passed config to the specified config path."""
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_config = serialize_config(
        config=config, output_format=config_path.suffix[1:])
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
            raise ConfigError(
                f"Format of config file {config_path} not in {{JSON, TOML}}")
    return config


def fill_static_config_defaults(raw_config: ConfigDict) -> ConfigDict:
    """Fill in the defaults of a raw static config dictionary."""
    context_default = raw_config.get("context_default", {})

    sync_defaults = update_dict_recursive(
        {"context": context_default},
        raw_config.get("sync", {}).get("defaults", {}))
    for sync_pair in (
            raw_config.get("sync", {}).get("pairs", {}).values()):
        sync_defaults_item = update_dict_recursive(
            sync_defaults, sync_pair.get("defaults", {}))
        sync_pair["source"] = update_dict_recursive(
            sync_defaults_item, sync_pair.get("source", {}))
        for target_config in sync_pair.get("targets", {}).values():
            target_config.update(
                update_dict_recursive(sync_defaults_item, target_config))

    thread_defaults = update_dict_recursive(
        {"context": context_default},
        raw_config.get("megathread", {}).get("defaults", {}))
    for thread in (
            raw_config.get("megathread", {}).get("megathreads", {}).values()):
        thread.update(
            update_dict_recursive(thread_defaults, thread))
        thread["source"] = update_dict_recursive(
            {"context": thread.get("context", {})}, thread["source"])
        thread["target_context"] = {
            **thread.get("context", {}), **thread.get("target_context", {})}

    return raw_config


def render_static_config(raw_config: ConfigDict) -> StaticConfig:
    """Transform the input config into an object with defaults filled in."""
    raw_config = dict(copy.deepcopy(raw_config))
    raw_config = fill_static_config_defaults(raw_config)
    static_config = StaticConfig.parse_obj(raw_config)
    return static_config


def load_static_config(
        config_path: PathLikeStr = CONFIG_PATH_STATIC) -> StaticConfig:
    """Load manager's static (user) config file, creating it if needed."""
    config_path = Path(config_path)
    example_config = EXAMPLE_STATIC_CONFIG.dict(exclude=EXAMPLE_EXCLUDE_FIELDS)
    if not config_path.exists():
        write_config(config=example_config, config_path=config_path)
    raw_config = load_config(config_path)
    if not raw_config:
        raise ConfigNotFoundError(
            f"Config file at {config_path.as_posix()} is empty.")
    static_config = render_static_config(raw_config)

    return static_config


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
        thread_config.post_title_template.strip().format(**template_vars))
    return template_vars


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
    subreddit_mod = reddit_mod.subreddit(thread_config.context.subreddit)
    reddit_post = accounts[thread_config.target_context.account]
    subreddit_post = reddit_post.subreddit(
        thread_config.target_context.subreddit)

    source_obj = create_sync_endpoint_from_config(
        config=thread_config.source,
        reddit=accounts[thread_config.source.context.account])

    template_vars = generate_template_vars(thread_config, dynamic_config)
    post_text = process_source_endpoint(
        thread_config.source, source_obj, dynamic_config)

    # Get current thread objects first
    current_thread = None
    current_thread_mod = None
    if dynamic_config.thread_id:
        current_thread = reddit_post.submission(id=dynamic_config.thread_id)
        current_thread_mod = reddit_mod.submission(id=dynamic_config.thread_id)

    # Submit and approve new thread
    new_thread = subreddit_post.submit(
        title=template_vars["post_title"], selftext=post_text)
    new_thread.disable_inbox_replies()
    new_thread_mod = reddit_mod.submission(id=new_thread.id)
    new_thread_mod.mod.approve()
    for attribute in ["id", "url", "permalink", "shortlink"]:
        template_vars[f"thread_{attribute}"] = getattr(new_thread, attribute)

    # Unpin old thread and pin new one
    if thread_config.pin_thread:
        bottom_sticky = thread_config.pin_thread != "top"
        if current_thread_mod:
            current_thread_mod.mod.sticky(state=False)
            time.sleep(10)
        try:
            sticky_to_keep = subreddit_mod.sticky(number=1)
            if current_thread and sticky_to_keep.id == current_thread.id:
                sticky_to_keep = subreddit_mod.sticky(number=2)
        except prawcore.exceptions.NotFound:
            sticky_to_keep = None
        new_thread_mod.mod.sticky(state=True, bottom=bottom_sticky)
        if sticky_to_keep:
            sticky_to_keep.mod.sticky(state=True)

    # Update links to point to new thread
    if current_thread and current_thread_mod:
        links = (
            tuple((getattr(thread, link_type).strip("/")
                   for thread in [current_thread, new_thread]))
            for link_type in ["permalink", "shortlink"])
        for idx, page_name in enumerate(thread_config.link_update_pages):
            page = WikiSyncEndpoint(
                endpoint_name=page_name,
                reddit=reddit_mod,
                subreddit=thread_config.context.subreddit,
                description=f"Megathread link page {idx + 1}",
                )
            new_content = page.content
            for old_link, new_link in links:
                new_content = re.sub(
                    pattern=re.escape(old_link),
                    repl=new_link,
                    string=new_content,
                    flags=re.IGNORECASE,
                    )
            page.edit(
                new_content,
                reason=f"Update {thread_config.description} megathread URLs")

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


def manage_thread(
        thread_config: ThreadConfig,
        dynamic_config: DynamicThreadConfig,
        accounts: AccountsMap,
        ) -> None:
    """Manage the current thread, creating or updating it as necessary."""
    if not thread_config.enabled:
        return

    reddit = accounts[thread_config.context.account]
    interval = thread_config.new_thread_interval

    # Determine if its time to post a new thread
    if interval:
        interval_unit, interval_n = process_raw_interval(interval)

        current_thread = reddit.submission(id=dynamic_config.thread_id)
        last_post_timestamp = datetime.datetime.fromtimestamp(
            current_thread.created_utc, tz=datetime.timezone.utc)
        current_datetime = datetime.datetime.now(datetime.timezone.utc)
        if interval_n is None:
            interval_exceeded = (
                getattr(last_post_timestamp, interval_unit)
                != getattr(current_datetime, interval_unit))
        else:
            delta_kwargs: dict[str, int] = {
                f"{interval_unit}s": interval_n}
            relative_timedelta = dateutil.relativedelta.relativedelta(
                **delta_kwargs)  # type: ignore[arg-type]
            interval_exceeded = (
                current_datetime > (
                    last_post_timestamp + relative_timedelta))
    else:
        interval_exceeded = False

    if interval_exceeded or not dynamic_config.thread_id:
        # If needed post a new thread
        print("Creating new thread for", thread_config.description)
        create_new_thread(thread_config, dynamic_config, accounts)
    else:
        # Otherwise, sync the current thread
        thread_target = FullEndpointConfig(
            context=thread_config.target_context,
            description=f"{thread_config.description} Megathread",
            endpoint_name=dynamic_config.thread_id,
            endpoint_type=EndpointType.THREAD,
            )
        sync_pair = SyncPairConfig(
            description=thread_config.description,
            source=thread_config.source,
            targets={"megathread": thread_target},
            )
        sync_one(
            sync_pair=sync_pair,
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
    try:
        # print("Source obj name:", source_obj.name,
        #       "Description:", source_obj.description)
        source_timestamp = source_obj.revision_date
    except NotImplementedError:  # Always update if source has no timestamp
        pass
    else:
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
            print("Sync pattern not found in source "
                  f"{source_obj.description}; skipping")
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
            print("Sync pattern not found in target "
                  f"{target_obj.description}; skipping")
            return False
        return target_content_processed

    return target_content


def sync_one(
        sync_pair: SyncPairConfig,
        dynamic_config: DynamicSyncConfig,
        accounts: AccountsMap,
        ) -> bool | None:
    """Sync one specific pair of sources and targets."""
    if not (sync_pair.enabled and sync_pair.source.enabled):
        return None
    if not sync_pair.targets:
        raise ConfigError(
            f"No sync targets specified for sync_pair {sync_pair.description}")

    source_obj = create_sync_endpoint_from_config(
        config=sync_pair.source,
        reddit=accounts[sync_pair.source.context.account])
    source_content = process_source_endpoint(
        sync_pair.source, source_obj, dynamic_config)
    if source_content is False:
        return False

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
            reason=f"Auto-sync {sync_pair.description} from {target_obj.name}",
            )
    return True


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


# ----------------- Setup and orchestration -----------------

def handle_refresh_tokens(
        accounts_config: AccountsConfig,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        ) -> Mapping[str, Mapping[str, Any]]:
    """Set up each account with the appropriate refresh tokens."""
    config_path_refresh = Path(config_path_refresh)
    accounts_config_processed = dict(copy.deepcopy(accounts_config))
    for account_key, account_kwargs in accounts_config_processed.items():
        account_kwargs = dict(account_kwargs)
        refresh_token = account_kwargs.pop("refresh_token", None)
        if refresh_token:
            # Initialize refresh token file
            token_path = config_path_refresh.with_name(
                config_path_refresh.name.format(key=account_key))
            if not token_path.exists():
                with open(token_path, "w",
                          encoding="utf-8", newline="\n") as token_file:
                    token_file.write(refresh_token)

            # Set up refresh token manager
            token_manager = praw.util.token_manager.FileTokenManager(
                token_path)
            account_kwargs["token_manager"] = token_manager

    return accounts_config_processed


def setup_accounts(
        accounts_config: AccountsConfig,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        ) -> AccountsMap:
    """Set up the praw.reddit objects for each account in the config."""
    accounts_config_processed = handle_refresh_tokens(
        accounts_config, config_path_refresh=config_path_refresh)
    accounts = {}
    for account_key, account_kwargs in accounts_config_processed.items():
        reddit = praw.Reddit(user_agent=USER_AGENT, **account_kwargs)
        reddit.validate_on_submit = True
        accounts[account_key] = reddit
    return accounts


def run_manage(
        config_path_static: PathLikeStr = CONFIG_PATH_STATIC,
        config_path_dynamic: PathLikeStr = CONFIG_PATH_DYNAMIC,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        ) -> None:
    """Load the config file and run the thread manager."""
    # Load config and set up session
    static_config = load_static_config(config_path_static)
    dynamic_config = load_dynamic_config(
        static_config=static_config, config_path=config_path_dynamic)
    dynamic_config_active = dynamic_config.copy(deep=True)
    accounts = setup_accounts(
        static_config.accounts, config_path_refresh=config_path_refresh)

    # Run the core manager tasks
    if static_config.sync.enabled:
        sync_all(static_config, dynamic_config_active, accounts)
    if static_config.megathread.enabled:
        manage_threads(static_config, dynamic_config_active, accounts)

    # Write out the dynamic config if it changed
    if dynamic_config_active != dynamic_config:
        write_config(dynamic_config_active, config_path=config_path_dynamic)


def run_manage_loop(
        config_path_static: PathLikeStr = CONFIG_PATH_STATIC,
        config_path_dynamic: PathLikeStr = CONFIG_PATH_DYNAMIC,
        config_path_refresh: PathLikeStr = CONFIG_PATH_REFRESH,
        repeat: float | bool = True,
        ) -> None:
    """Run the mainloop of sub-manager, performing each task in sequance."""
    static_config = load_static_config(config_path=config_path_static)
    load_dynamic_config(
        static_config=static_config, config_path=config_path_dynamic)

    # If default config was generated or config was unmodified, return
    if static_config.accounts == EXAMPLE_ACCOUNTS:
        print("Default config file generated at",
              Path(config_path_static).as_posix())
        return

    if repeat is True:
        repeat = static_config.repeat_interval_s
    while True:
        print(f"Running megathread manager for config at {config_path_static}")
        run_manage(
            config_path_static=config_path_static,
            config_path_dynamic=config_path_dynamic,
            config_path_refresh=config_path_refresh,
            )
        print("Megathread manager run complete")
        if not repeat:
            break
        try:
            time_left_s = repeat
            while True:
                time_to_sleep_s = min((time_left_s, 1))
                time.sleep(time_to_sleep_s)
                time_left_s -= 1
                if time_left_s <= 0:
                    break
        except KeyboardInterrupt:
            print("Recieved keyboard interrupt; exiting")
            break


def main(sys_argv: list[str] | None = None) -> None:
    """Run the main function for the Megathread Manager CLI and dispatch."""
    parser_main = argparse.ArgumentParser(
        description="Generate, post, update and pin a Reddit megathread.",
        argument_default=argparse.SUPPRESS)
    parser_main.add_argument(
        "--version",
        action="store_true",
        help="If passed, will print the version number and exit",
        )
    parser_main.add_argument(
        "--config-path", dest="config_path_static",
        help="The path to a custom static (user) config file to use.",
        )
    parser_main.add_argument(
        "--dynamic-config-path", dest="config_path_dynamic",
        help="The path to a custom dynamic (runtime) config file to use.",
        )
    parser_main.add_argument(
        "--refresh-config-path", dest="config_path_refresh",
        help="The path to a custom (set of) refresh token files to use.",
        )
    parser_main.add_argument(
        "--repeat",
        nargs="?",
        default=False,
        const=True,
        type=int,
        metavar="N",
        help=("If passed, re-runs every N seconds, or the value from the "
              "config file variable repeat_interval_s if N isn't specified."),
        )
    parsed_args = parser_main.parse_args(sys_argv)

    if getattr(parsed_args, "version", False):
        print(f"Megathread Manager version {__version__}")
    else:
        try:
            run_manage_loop(**vars(parsed_args))
        except ConfigNotFoundError as e:
            print(f"Default config file generated. {e}")


if __name__ == "__main__":
    main()
