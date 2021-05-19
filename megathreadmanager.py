#!/usr/bin/env python3
"""
Generate, pin and update a regular megathread for a subreddit.
"""

# Standard library imports
import abc
import argparse
import copy
import datetime
import enum
import json
from pathlib import Path
import re
import time

# Third party imports
import dateutil.relativedelta
import praw
import praw.util.token_manager
import prawcore.exceptions
import toml


# ----------------- Constants -----------------

__version__ = "0.5.0"

# General constants
CONFIG_DIRECTORY = Path("~/.config/megathread-manager").expanduser()
CONFIG_PATH_STATIC = CONFIG_DIRECTORY / "config.toml"
CONFIG_PATH_DYNAMIC = CONFIG_DIRECTORY / "config_dynamic.json"
CONFIG_PATH_REFRESH = CONFIG_DIRECTORY / "refresh_token_{account_key}.txt"
USER_AGENT = f"praw:megathreadmanager:v{__version__} (by u/CAM-Gerlach)"


# Enum values
@enum.unique
class EndpointType(enum.Enum):
    MENU = enum.auto()
    THREAD = enum.auto()
    WIDGET = enum.auto()
    WIKI_PAGE = enum.auto()


# Config
DEFAULT_REDIRECT_TEMPLATE = """
This thread is no longer being updated, and has been replaced by:

# [{post_title}]({thread_url})
"""

DEFAULT_SYNC_ENDPOINT = {
    "description": "",
    "enabled": True,
    "endpoint_name": "",
    "endpoint_type": EndpointType.WIKI_PAGE.name,
    "menu_config": {},
    "pattern": False,
    "pattern_end": " End",
    "pattern_start": " Start",
    "replace_patterns": {},
    }

DEFAULT_SYNC_PAIR = {
    "defaults": {},
    "description": "",
    "enabled": True,
    "source": {},
    "targets": {},
    }

DEFAULT_MEGATHREAD_CONFIG = {
    "defaults": {},
    "description": "",
    "enabled": True,
    "initial": {
        "thread_number": 0,
        "thread_id": "",
        },
    "link_update_pages": [],
    "new_thread_interval": "month",
    "new_thread_redirect_op": False,
    "new_thread_redirect_sticky": False,
    "new_thread_redirect_template": DEFAULT_REDIRECT_TEMPLATE,
    "pin_thread": "top",
    "post_title_template": ("{subreddit} Megathread (#{thread_number})"),
    "source": {},
    }

DYNAMIC_CONFIGS = {
    "megathread": {
        "static_config_path": ("megathread", "megathreads"),
        "defaults": {
            "thread_number": 0,
            "thread_id": "",
            "source_timestamp": 0,
            },
        },
    "sync": {
        "static_config_path": ("sync", "pairs"),
        "defaults": {
            "source_timestamp": 0,
            },
        },
    }

DEFAULT_CONFIG = {
    "repeat_interval_s": 60,
    "accounts": {
        "example": {
            "site_name": "EXAMPLE",
            },
        },
    "defaults": {
        "account": "example",
        "subreddit": "YOURSUBNAMEHERE",
        },
    "megathread": {
        "enabled": True,
        "defaults": {
            "new_thread_redirect_template": DEFAULT_REDIRECT_TEMPLATE,
            },
        "megathreads": {
            "example_primary": {
                "description": "Primary megathread",
                "enabled": False,
                "initial": {
                    "thread_number": 0,
                    "thread_id": "",
                    },
                "link_update_pages": [],
                "new_thread_interval": "month",
                "pin_thread": "top",
                "post_title_template": ("{subreddit} Megathread "
                                        "({current_datetime:%B %Y}, "
                                        "#{thread_number})"),
                "source": {
                    "description": "Megathreads wiki page",
                    "endpoint_name": "threads",
                    "replace_patterns": {
                        "https://old.reddit.com": "https://www.reddit.com",
                        },
                    },
                },
            },
        },
    "sync": {
        "enabled": True,
        "defaults": {
            "pattern_end": " End",
            "pattern_start": " Start",
            },
        "pairs": {
            "example_sidebar": {
                "description": "Sync Sidebar Demo",
                "enabled": False,
                "source": {
                    "description": "Thread source wiki page",
                    "endpoint_name": "threads",
                    "endpoint_type": EndpointType.WIKI_PAGE.name,
                    "pattern": "Sidebar",
                    "replace_patterns": {
                        "https://www.reddit.com": "https://old.reddit.com",
                        },
                    },
                "targets": {
                    "sidebar": {
                        "description": "Sub Sidebar",
                        "enabled": True,
                        "endpoint_name": "config/sidebar",
                        "endpoint_type": EndpointType.WIKI_PAGE.name,
                        "pattern": "Sidebar",
                        "replace_patterns": {},
                        },
                    },
                },
            },
        },
    }


# ----------------- Helper functions -----------------

def replace_patterns(text, patterns):
    for old, new in patterns.items():
        text = text.replace(old, new)
    return text


def startend_to_pattern(start, end=None):
    end = start if end is None else end
    pattern = r"(?<={start})(\s|\S)*(?={end})".format(
        start=re.escape(start), end=re.escape(end))
    return pattern


def startend_to_pattern_md(start, end=None):
    end = start if end is None else end
    start, end = [f"[](/# {pattern})" for pattern in (start, end)]
    return startend_to_pattern(start, end)


def search_startend(source_text, pattern="", start="", end=""):
    if pattern is False or pattern is None or not (pattern or start or end):
        return False
    start = pattern + start
    end = pattern + end
    pattern = startend_to_pattern_md(start, end)
    match_obj = re.search(pattern, source_text)
    return match_obj


def split_and_clean_text(source_text, split):
    source_text = source_text.strip()
    if split:
        sections = source_text.split(split)
    else:
        sections = [source_text]
    sections = [section.strip() for section in sections if section.strip()]
    return sections


def extract_text(pattern, source_text):
    match = re.search(pattern, source_text)
    if not match:
        return False
    match_text = match.groups()[0] if match.groups() else match.group()
    return match_text


def process_raw_interval(raw_interval):
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


# ----------------- Helper classes -----------------

class ConfigError(RuntimeError):
    pass


class ConfigNotFoundError(ConfigError):
    pass


class SyncEndpoint(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __init__(self, endpoint_name, reddit, subreddit, description=None):
        self.name = endpoint_name
        self.description = endpoint_name if not description else description
        self._object = None
        self._reddit = reddit
        self._subreddit = self._reddit.subreddit(subreddit)

    @property
    @abc.abstractmethod
    def content(self):
        pass

    def edit(self, new_content, reason=""):  # pylint: disable=unused-argument
        self._object.edit(new_content)

    @content.setter
    def content(self, new_content):
        self.edit(new_content)

    @property
    @abc.abstractmethod
    def revision_date(self):
        pass


class MenuSyncEndpoint(SyncEndpoint):
    def __init__(self, **kwargs):
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
    def content(self):
        return self._object.data

    def edit(self, new_content, reason=""):
        self._object.mod.update(data=new_content)

    @property
    def revision_date(self):
        raise NotImplementedError


class ThreadSyncEndpoint(SyncEndpoint):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._object = self._reddit.submission(id=self.name)

    @property
    def content(self):
        return self._object.selftext

    @property
    def revision_date(self):
        edited = self._object.edited
        return edited if edited else self._object.created_utc


class WidgetSyncEndpoint(SyncEndpoint):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for widget in self._subreddit.widgets.sidebar:
            if widget.shortName == self.name:
                self._object = widget
                break
        else:
            raise ValueError(
                f"Widget {self.name} missing for endpoint {self.description}")

    @property
    def content(self):
        return self._object.text

    def edit(self, new_content, reason=""):
        self._object.mod.update(text=new_content)

    @property
    def revision_date(self):
        raise NotImplementedError


class WikiSyncEndpoint(SyncEndpoint):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._object = self._subreddit.wiki[self.name]

    @property
    def content(self):
        return self._object.content_md

    def edit(self, new_content, reason=""):
        self._object.edit(new_content, reason=reason)

    @property
    def revision_date(self):
        return self._object.revision_date


SYNC_ENDPOINT_TYPES = {
    EndpointType.MENU: MenuSyncEndpoint,
    EndpointType.THREAD: ThreadSyncEndpoint,
    EndpointType.WIDGET: WidgetSyncEndpoint,
    EndpointType.WIKI_PAGE: WikiSyncEndpoint,
    }

SYNC_ENDPOINT_PARAMETERS = {
    "description", "endpoint_name", "endpoint_type", "reddit", "subreddit"}


def create_sync_endpoint(
        endpoint_type=EndpointType.WIKI_PAGE, **endpoint_kwargs):
    if not isinstance(endpoint_type, EndpointType):
        endpoint_type = EndpointType[endpoint_type]
    sync_endpoint = SYNC_ENDPOINT_TYPES[endpoint_type](**endpoint_kwargs)
    return sync_endpoint


def create_sync_endpoint_from_config(config, reddit):
    filtered_kwargs = {key: value for key, value in config.items()
                       if key in SYNC_ENDPOINT_PARAMETERS}
    return create_sync_endpoint(reddit=reddit, **filtered_kwargs)


# ----------------- Config functions -----------------

def handle_refresh_tokens(accounts, config_path_refresh=CONFIG_PATH_REFRESH):
    """Setup each account with the appropriate refresh tokens."""
    for account_key, account_kwargs in accounts.items():
        refresh_token = account_kwargs.pop("refresh_token", None)
        if refresh_token:
            # Initialize refresh token file
            token_path = config_path_refresh.with_name(
                config_path_refresh.name.format(account_key=account_key))
            if not token_path.exists():
                with open(token_path, "w",
                          encoding="utf-8", newline="\n") as token_file:
                    token_file.write(refresh_token)

            # Set up refresh token manager
            token_manager = praw.util.token_manager.FileTokenManager(
                token_path)
            account_kwargs["token_manager"] = token_manager

    return accounts


def write_config(config, config_path=CONFIG_PATH_DYNAMIC):
    """Write the passed config to the specified config path."""
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, mode="w",
              encoding="utf-8", newline="\n") as config_file:
        if config_path.suffix == ".json":
            json.dump(config, config_file, indent=4)
        elif config_path.suffix == ".toml":
            toml.dump(config, config_file)
        else:
            raise ConfigError(
                f"Format of config file {config_path} not in {{JSON, TOML}}")


def load_config(config_path):
    """Load the config file at the specified path."""
    config_path = Path(config_path)
    with open(config_path, mode="r", encoding="utf-8") as config_file:
        if config_path.suffix == ".json":
            config = json.load(config_file)
        elif config_path.suffix == ".toml":
            config = toml.load(config_file)
        else:
            raise ConfigError(
                f"Format of config file {config_path} not in {{JSON, TOML}}")
    return config


def load_static_config(
        config_path=CONFIG_PATH_STATIC,
        config_path_refresh=CONFIG_PATH_REFRESH):
    """Load manager's static (user) config file, creating it if needed."""
    if not Path(config_path).exists():
        write_config(DEFAULT_CONFIG, config_path=config_path)
    static_config = load_config(config_path)
    static_config = {**DEFAULT_CONFIG, **static_config}
    if not static_config or static_config == DEFAULT_CONFIG:
        raise ConfigNotFoundError(
            f"Config file at {config_path} needs to be set up.")
    static_config["accounts"] = handle_refresh_tokens(
        static_config["accounts"], config_path_refresh=config_path_refresh)

    return static_config


def render_dynamic_config(static_config=None, dynamic_config=None):
    """Generate the dynamic config, filling defaults as needed."""
    # Set up existing config
    if static_config is None:
        static_config = load_static_config()
    if dynamic_config is None:
        dynamic_config = {}

    # Fill defaults in dynamic config
    for dynamic_config_key, config_params in DYNAMIC_CONFIGS.items():
        dynamic_config_section = dynamic_config.get(dynamic_config_key, {})

        static_config_items = static_config
        for path_element in config_params["static_config_path"]:
            static_config_items = static_config_items.get(path_element, {})

        for config_id, static_config_item in static_config_items.items():
            initial_dynamic_config = static_config_item.get("initial", {})
            dynamic_config_section[config_id] = {
                **config_params["defaults"],
                **initial_dynamic_config,
                **dynamic_config_section.get(config_id, {}),
                }
        dynamic_config[dynamic_config_key] = dynamic_config_section

    return dynamic_config


def load_dynamic_config(config_path=CONFIG_PATH_DYNAMIC, static_config=None):
    """Load manager's dynamic runtime config file, creating it if needed."""
    if not Path(config_path).exists():
        dynamic_config = render_dynamic_config(
            static_config=static_config, dynamic_config={})
        write_config(dynamic_config, config_path=config_path)
    else:
        dynamic_config = load_config(config_path)
        dynamic_config = render_dynamic_config(
            static_config=static_config, dynamic_config=dynamic_config)

    return dynamic_config


# ----------------- Core megathread logic -----------------

def generate_template_vars(thread_config, dynamic_config):
    """Generate the title and post templates."""
    template_vars = {
        "current_datetime": datetime.datetime.now(datetime.timezone.utc),
        "current_datetime_local": datetime.datetime.now(),
        "subreddit": thread_config["subreddit"],
        "thread_number": dynamic_config["thread_number"],
        "thread_number_previous": dynamic_config["thread_number"] - 1,
        "thread_id_previous": dynamic_config["thread_id"],
        }
    template_vars["post_title"] = (
        thread_config["post_title_template"].strip().format(**template_vars))
    return template_vars


def create_new_thread(thread_config, dynamic_config, accounts):
    """Create a new thread based on the title and post template."""
    # Generate thread title and contents
    dynamic_config["source_timestamp"] = 0
    dynamic_config["thread_number"] += 1
    description = thread_config["description"]

    # Get subreddit objects for thread
    reddit_mod = accounts[thread_config["account"]]
    subreddit_mod = reddit_mod.subreddit(thread_config["subreddit"])
    target_config = {**thread_config["defaults"], **thread_config["target"]}
    reddit_post = accounts[target_config["account"]]
    subreddit_post = reddit_post.subreddit(target_config["subreddit"])

    source_config = {
        **DEFAULT_SYNC_ENDPOINT,
        **thread_config["defaults"],
        **thread_config["source"],
        }
    source_obj = create_sync_endpoint_from_config(
        config=source_config, reddit=accounts[source_config["account"]])

    template_vars = generate_template_vars(thread_config, dynamic_config)
    post_text = process_source_endpoint(
        source_config, source_obj, dynamic_config)
    post_title = template_vars["post_title"]

    # Submit and approve new thread
    thread_id = dynamic_config["thread_id"]
    if thread_id:
        current_thread = reddit_post.submission(id=thread_id)
        current_thread_mod = reddit_mod.submission(id=thread_id)
    else:
        current_thread = None
        current_thread_mod = None

    new_thread = subreddit_post.submit(title=post_title, selftext=post_text)
    new_thread.disable_inbox_replies()
    new_thread_mod = reddit_mod.submission(id=new_thread.id)
    new_thread_mod.mod.approve()
    for attribute in ["id", "url", "permalink", "shortlink"]:
        template_vars[f"thread_{attribute}"] = getattr(new_thread, attribute)

    # Unpin old thread and pin new one
    if thread_config["pin_thread"]:
        bottom_sticky = thread_config["pin_thread"] != "top"
        if current_thread:
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
    if current_thread:
        links = (
            tuple((getattr(thread, link_type).strip("/")
                   for thread in [current_thread, new_thread]))
            for link_type in ["permalink", "shortlink"])
        for idx, page_name in enumerate(thread_config["link_update_pages"]):
            page = create_sync_endpoint(
                description=f"Megathread link page {idx + 1}",
                endpoint_name=page_name,
                endpoint_type=EndpointType.WIKI_PAGE,
                reddit=reddit_mod,
                subreddit=thread_config["subreddit"],
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
                new_content, reason=f"Update {description} megathread URLs")

        # Add messages to new thread on old thread if enabled
        redirect_template = thread_config["new_thread_redirect_template"]
        redirect_message = redirect_template.strip().format(**template_vars)

        if thread_config["new_thread_redirect_op"]:
            current_thread.edit(
                redirect_message + "\n\n" + current_thread.selftext)
        if thread_config["new_thread_redirect_sticky"]:
            redirect_comment = current_thread_mod.reply(redirect_message)
            redirect_comment.mod.distinguish(sticky=True)

    # Update config accordingly
    dynamic_config["thread_id"] = new_thread.id


def manage_thread(thread_config, dynamic_config, accounts):
    """Manage the current thread, creating or updating it as necessary."""
    if not thread_config["enabled"]:
        return

    reddit = accounts[thread_config["account"]]
    interval = thread_config["new_thread_interval"]
    if interval:
        interval_unit, interval_n = process_raw_interval(interval)

        if dynamic_config["thread_id"]:
            current_thread = reddit.submission(id=dynamic_config["thread_id"])
            last_post_timestamp = datetime.datetime.fromtimestamp(
                current_thread.created_utc, tz=datetime.timezone.utc)
            current_datetime = datetime.datetime.now(datetime.timezone.utc)
            if interval_n is None:
                should_post_new_thread = (
                    getattr(last_post_timestamp, interval_unit)
                    != getattr(current_datetime, interval_unit))
            else:
                delta_kwargs = {interval_unit + "s": interval_n}
                should_post_new_thread = (
                    current_datetime
                    > (last_post_timestamp
                       + dateutil.relativedelta.relativedelta(**delta_kwargs)))
        else:
            should_post_new_thread = True
    else:
        should_post_new_thread = False

    if should_post_new_thread:
        print("Creating new thread for '{}'".format(
            thread_config.get('description', dynamic_config["thread_id"])))
        create_new_thread(thread_config, dynamic_config, accounts)
    else:
        sync_pair = {key: value for key, value in thread_config.items()
                     if key in {"defaults", "source"}}
        sync_pair = {**DEFAULT_SYNC_PAIR, **sync_pair}
        target = {
            "description": f"{thread_config['description']} Megathread",
            "endpoint_name": dynamic_config["thread_id"],
            "endpoint_type": EndpointType.THREAD,
            }
        sync_pair["targets"] = {
            "megathread": {**target, **thread_config["target"]}}
        sync_one(
            sync_pair=sync_pair,
            dynamic_config=dynamic_config,
            accounts=accounts,
            )


def manage_threads(static_config, dynamic_config, accounts):
    """Check and create/update all defined megathreads for a sub."""
    defaults = {
        **static_config["defaults"],
        **static_config["megathread"]["defaults"],
        }
    for thread_id, thread_config in (
            static_config["megathread"]["megathreads"].items()):
        thread_config = {**DEFAULT_MEGATHREAD_CONFIG, **thread_config}
        thread_config["defaults"] = {**defaults, **thread_config["defaults"]}
        thread_config = {
            **thread_config["defaults"], **thread_config}
        dynamic_config_thread = dynamic_config["megathread"][thread_id]

        manage_thread(
            thread_config=thread_config,
            dynamic_config=dynamic_config_thread,
            accounts=accounts,
            )


# ----------------- Sync functionality -----------------

def parse_menu(
        source_text,
        split="\n\n",
        subsplit="\n",
        pattern_title=r"\[([^\n\]]*)\]\(",
        pattern_url=r"\]\(([^\s\)]*)[\s\)]",
        pattern_subtitle=r"\[([^\n\]]*)\]\(",
        ):
    menu_data = []
    source_text = source_text.replace("\r\n", "\n")
    menu_sections = split_and_clean_text(
        source_text, split)
    for menu_section in menu_sections:
        menu_subsections = split_and_clean_text(
            menu_section, subsplit)
        if not menu_subsections:
            continue
        title_text = extract_text(
            pattern_title, menu_subsections[0])
        if title_text is False:
            continue
        section_data = {"text": title_text}
        if len(menu_subsections) == 1:
            url_text = extract_text(
                pattern_url, menu_subsections[0])
            if url_text is False:
                continue
            section_data["url"] = url_text
        else:
            children = []
            for menu_child in menu_subsections[1:]:
                title_text = extract_text(
                    pattern_subtitle, menu_child)
                url_text = extract_text(
                    pattern_url, menu_child)
                if title_text is not False and url_text is not False:
                    children.append(
                        {"text": title_text, "url": url_text})
            section_data["children"] = children
        menu_data.append(section_data)
    return menu_data


def process_endpoint_text(content, config, replace_text=None):
    match_obj = search_startend(
        content, config["pattern"],
        config["pattern_start"], config["pattern_end"])
    if match_obj is not False:
        if not match_obj:
            return False
        output_text = match_obj.group()
        if replace_text is not None:
            output_text = content.replace(output_text, replace_text)
        return output_text

    return content if replace_text is None else replace_text


def process_source_endpoint(source_config, source_obj, dynamic_config):
    try:
        # print("Source obj name:", source_obj.name,
        #       "Description:", source_obj.description)
        source_timestamp = source_obj.revision_date
    except NotImplementedError:  # Always update if source has no timestamp
        pass
    else:
        source_updated = (
            source_timestamp > dynamic_config["source_timestamp"])
        if not source_updated:
            return False
        dynamic_config["source_timestamp"] = source_timestamp

    source_content = source_obj.content
    if isinstance(source_content, str):
        source_content = process_endpoint_text(source_content, source_config)
        if source_content is False:
            print("Sync pattern not found in source "
                  f"{source_obj.description}; skipping")
            return False
        source_content = replace_patterns(
            source_content, source_config["replace_patterns"])

    return source_content


def process_target_endpoint(target_config, target_obj, source_content):
    if isinstance(source_content, str):
        source_content = replace_patterns(
            source_content, target_config["replace_patterns"])

    target_content = target_obj.content
    if (isinstance(target_obj, MenuSyncEndpoint)
            and isinstance(source_content, str)):
        target_content = parse_menu(
            source_text=source_content, **target_config["menu_config"])
    elif isinstance(target_content, str):
        target_content = process_endpoint_text(
            target_content, target_config, replace_text=source_content)
        if target_content is False:
            print("Sync pattern not found in target "
                  f"{target_obj.description}; skipping")
            return False

    return target_content


def sync_one(sync_pair, dynamic_config, accounts):
    """Sync one specific pair of sources and targets."""
    description = sync_pair.get("description", "Unnamed")
    defaults = {**DEFAULT_SYNC_ENDPOINT, **sync_pair["defaults"]}
    source_config = {**defaults, **sync_pair["source"]}

    if not (sync_pair["enabled"] or source_config["enabled"]):
        return None
    if not sync_pair["targets"]:
        raise ConfigError(
            f"No sync targets specified for sync_pair {description}")

    source_obj = create_sync_endpoint_from_config(
        config=source_config, reddit=accounts[source_config["account"]])
    source_content = process_source_endpoint(
        source_config, source_obj, dynamic_config)
    if source_content is False:
        return False

    for target_config in sync_pair["targets"].values():
        target_config = {**defaults, **target_config}
        if not target_config["enabled"]:
            continue

        target_obj = create_sync_endpoint_from_config(
            config=target_config, reddit=accounts[target_config["account"]])
        target_content = process_target_endpoint(
            target_config, target_obj, source_content)
        if target_content is False:
            continue

        target_obj.edit(
            target_content,
            reason=f"Auto-sync {description} from {target_obj.name}",
            )
    return True


def sync_all(static_config, dynamic_config, accounts):
    """Sync all pairs of sources/targets (pages,threads, sections) on a sub."""
    defaults = {
        **static_config["defaults"],
        **static_config["sync"]["defaults"],
        }
    for sync_pair_id, sync_pair in static_config["sync"]["pairs"].items():
        sync_pair = {**DEFAULT_SYNC_PAIR, **sync_pair}
        sync_pair["defaults"] = {**defaults, **sync_pair["defaults"]}
        dynamic_config_sync = dynamic_config["sync"][sync_pair_id]

        sync_one(
            sync_pair=sync_pair,
            dynamic_config=dynamic_config_sync,
            accounts=accounts,
            )


# ----------------- Orchestration -----------------

def setup_accounts(accounts_config):
    accounts = {}
    for account_key, account_kwargs in accounts_config.items():
        reddit = praw.Reddit(user_agent=USER_AGENT, **account_kwargs)
        reddit.validate_on_submit = True
        accounts[account_key] = reddit
    return accounts


def run_manage(
        config_path_static=CONFIG_PATH_STATIC,
        config_path_dynamic=CONFIG_PATH_DYNAMIC,
        config_path_refresh=CONFIG_PATH_REFRESH,
        ):
    """Load the config file and run the thread manager."""
    # Load config and set up session
    static_config = load_static_config(config_path_static, config_path_refresh)
    dynamic_config = load_dynamic_config(config_path_dynamic, static_config)
    dynamic_config_active = copy.deepcopy(dynamic_config)
    accounts = setup_accounts(static_config["accounts"])

    # Run the core manager tasks
    if static_config["sync"]["enabled"]:
        sync_all(static_config, dynamic_config_active, accounts)
    if static_config["megathread"]["enabled"]:
        manage_threads(static_config, dynamic_config_active, accounts)

    # Write out the dynamic config if it changed
    if dynamic_config_active != dynamic_config:
        write_config(dynamic_config_active, config_path=config_path_dynamic)


def run_manage_loop(
        config_path_static=CONFIG_PATH_STATIC,
        config_path_dynamic=CONFIG_PATH_DYNAMIC,
        config_path_refresh=CONFIG_PATH_REFRESH,
        repeat=True,
        ):
    static_config = load_static_config(config_path=config_path_static)
    if repeat is True:
        repeat = static_config.get(
            "repeat_interval_s", DEFAULT_CONFIG["repeat_interval_s"])
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


def main(sys_argv=None):
    """Main function for the Megathread Manager CLI and dispatch."""
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
