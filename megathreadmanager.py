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
import praw
import prawcore.exceptions
import tomlkit


# ----------------- Constants -----------------

__version__ = "0.3.0dev0"

# General constants
CONFIG_DIRECTORY = Path("~/.config/megathread-manager").expanduser()
CONFIG_PATH_STATIC = CONFIG_DIRECTORY / "config.toml"
CONFIG_PATH_DYNAMIC = CONFIG_DIRECTORY / "config_dynamic.json"
USER_AGENT = f"praw:megathreadmanager:v{__version__} (by u/CAM-Gerlach)"


# Enum values
@enum.unique
class EndpointType(enum.Enum):
    MENU = enum.auto()
    THREAD = enum.auto()
    WIDGET = enum.auto()
    WIKI_PAGE = enum.auto()


# Config
DEFAULT_SYNC_ENDPOINT = {
    "description": "",
    "enabled": True,
    "endpoint_name": "",
    "endpoint_type": EndpointType.WIKI_PAGE.name,
    "menu_config": {},
    "pattern": "",
    "pattern_end": " End",
    "pattern_start": " Start",
    "replace_patterns": {},
    }

DEFAULT_SYNC_PAIR = {
    "description": "",
    "enabled": True,
    "source": {},
    "targets": {},
    }

DEFAULT_MEGATHREAD_CONFIG = {
    "description": "",
    "enabled": True,
    "initial": {
        "thread_number": 0,
        "thread_id": "",
        },
    "link_update_pages": [],
    "new_thread_interval": "month",
    "pin_thread": "top",
    "post_title_template": ("{subreddit_name} Megathread "
                            "({current_datetime:%B %Y}, #{thread_number})"),
    "replace_patterns": {},
    }

DEFAULT_DYNAMIC_CONFIGS = {
    "megathreads": {
        "thread_number": 0,
        "thread_id": "",
        "source_timestamp": 0,
        },
    "sync_pairs": {
        "source_timestamp": 0,
        },
    }

DEFAULT_CONFIG = {
    "credentials_praw": {
        "DEFAULT": {},
        "mod": {},
        "post": {},
        },
    "megathreads_enabled": True,
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
            "post_title_template": ("{subreddit_name} Megathread "
                                    "({current_datetime:%B %Y}, "
                                    "#{thread_number})"),
            "replace_patterns": {
                "https://old.reddit.com": "https://www.reddit.com",
                },
            "source_name": "threads",
            },
        },
    "repeat_interval_s": 60,
    "subreddit_name": "YOURSUBNAME",
    "sync_enabled": True,
    "sync_pairs": {
        "example_sidebar": {
            "description": "Sync Sidebar Demo",
            "source": {
                "description": "Thread source wiki page",
                "enabled": False,
                "endpoint_name": "threads",
                "endpoint_type": EndpointType.WIKI_PAGE.name,
                "pattern": "Sidebar",
                "pattern_end": " End",
                "pattern_start": " Start",
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
                    "pattern_end": " Start",
                    "pattern_start": " End",
                    "replace_patterns": {},
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


# ----------------- Helper classes -----------------

class ConfigError(RuntimeError):
    pass


class ConfigNotFoundError(ConfigError):
    pass


class MegathreadUserSession:
    """Cached state specific to a Reddit user."""

    def __init__(self, config, credential_key):
        self.reddit = praw.Reddit(**{
            **config["credentials_praw"].get("DEFAULT", {}),
            **config["credentials_praw"].get(credential_key, {}),
            **{"user_agent": USER_AGENT},
            })
        self.subreddit = self.reddit.subreddit(
            config["subreddit_name"])


class MegathreadSession:
    """Common cached state for managing megathreads."""

    def __init__(self, static_config, dynamic_config):
        self.config = static_config
        self.dynamic_config = dynamic_config
        self.user = MegathreadUserSession(
            config=self.config, credential_key="post")
        self.mod = MegathreadUserSession(
            config=self.config, credential_key="mod")


class SyncEndpoint(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __init__(
            self,
            endpoint_name,
            reddit=None,
            subreddit=None,
            description=None,
                ):
        self.name = endpoint_name
        self.description = endpoint_name if not description else description
        self._object = None

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
    def __init__(self, subreddit, **kwargs):
        super().__init__(**kwargs)
        if not self.name:
            self.name = "menu"
        for widget in subreddit.widgets.topbar:
            if widget.kind == self.name:
                self._object = widget
                break
        else:
            print("Menu widget not found; assuming its first in the topbar")
            self._object = subreddit.widgets.topbar[0]

    @property
    def content(self):
        return self._object.data

    def edit(self, new_content, reason=""):
        self._object.mod.update(data=new_content)

    @property
    def revision_date(self):
        raise NotImplementedError


class ThreadSyncEndpoint(SyncEndpoint):
    def __init__(self, reddit, **kwargs):
        super().__init__(**kwargs)
        self._object = reddit.submission(id=self.name)

    @property
    def content(self):
        return self._object.selftext

    @property
    def revision_date(self):
        edited = self._object.edited
        return edited if edited else self._object.created_utc


class WidgetSyncEndpoint(SyncEndpoint):
    def __init__(self, subreddit, **kwargs):
        super().__init__(**kwargs)
        for widget in subreddit.widgets.sidebar:
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
    def __init__(self, subreddit, **kwargs):
        super().__init__(**kwargs)
        self._object = subreddit.wiki[self.name]

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


def create_sync_endpoint(
        endpoint_type=EndpointType.WIKI_PAGE, **endpoint_kwargs):
    if not isinstance(endpoint_type, EndpointType):
        endpoint_type = EndpointType[endpoint_type]
    sync_endpoint = SYNC_ENDPOINT_TYPES[endpoint_type](**endpoint_kwargs)
    return sync_endpoint


def create_sync_endpoint_from_config(config, reddit, subreddit):
    config = {key: value for key, value in config.items()
              if key in {"endpoint_name", "endpoint_type", "description"}}
    return create_sync_endpoint(reddit=reddit, subreddit=subreddit, **config)


# ----------------- Config functions -----------------

def write_config(config, config_path=CONFIG_PATH_DYNAMIC):
    """Write the passed config to the specified config path."""
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, mode="w",
              encoding="utf-8", newline="\n") as config_file:
        if config_path.suffix == ".json":
            json.dump(config, config_file, indent=4)
        elif config_path.suffix == ".toml":
            config_raw = tomlkit.dumps(config)
            config_file.write(config_raw)
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
            config_raw = config_file.read()
            config = dict(tomlkit.loads(config_raw))
        else:
            raise ConfigError(
                f"Format of config file {config_path} not in {{JSON, TOML}}")
    return config


def load_static_config(config_path=CONFIG_PATH_STATIC):
    """Load manager's static (user) config file, creating it if needed."""
    if not Path(config_path).exists():
        write_config(DEFAULT_CONFIG, config_path=config_path)
    static_config = load_config(config_path)
    static_config = {**DEFAULT_CONFIG, **static_config}
    if not static_config or static_config == DEFAULT_CONFIG:
        raise ConfigNotFoundError(
            f"Config file at {config_path} needs to be set up.")
    return static_config


def render_dynamic_config(static_config=None, dynamic_config=None):
    """Generate the dynamic config, filling defaults as needed."""
    # Set up existing config
    if static_config is None:
        static_config = load_static_config()
    if dynamic_config is None:
        dynamic_config = {}

    # Fill defaults in dynamic config
    for config_key, defaults in DEFAULT_DYNAMIC_CONFIGS.items():
        config_section = dynamic_config.get(config_key, {})
        for config_id, static_config_item in static_config[config_key].items():
            initial = static_config_item.get("initial", {})
            config_section[config_id] = {
                **defaults, **initial, **config_section.get(config_id, {})}
        dynamic_config[config_key] = config_section

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

def generate_post_details(session, thread_config, dynamic_config):
    """Generate the title and post templates."""
    template_variables = {
        "current_datetime": datetime.datetime.now(datetime.timezone.utc),
        "current_datetime_local": datetime.datetime.now(),
        "subreddit_name": session.config["subreddit_name"],
        "thread_number": dynamic_config["thread_number"],
        "thread_id": dynamic_config["thread_id"],
        }
    post_title = thread_config["post_title_template"].format(
        **template_variables)
    source_page = session.mod.subreddit.wiki[thread_config["source_name"]]
    post_text = source_page.content_md.format(**template_variables)
    post_text = replace_patterns(post_text, thread_config["replace_patterns"])
    return {"title": post_title, "selftext": post_text}


def update_current_thread(session, thread_config, dynamic_config):
    """Update the text of the current thread."""
    post_details = generate_post_details(
        session, thread_config, dynamic_config)
    current_thread = session.user.reddit.submission(
        id=dynamic_config["thread_id"])
    current_thread.edit(post_details["selftext"])


def create_new_thread(session, thread_config, dynamic_config):
    """Create a new thread based on the title and post template."""
    dynamic_config["thread_number"] += 1
    post_details = generate_post_details(
        session, thread_config, dynamic_config)

    # Submit and approve new thread
    thread_id = dynamic_config["thread_id"]
    if thread_id:
        current_thread = session.user.reddit.submission(id=thread_id)
    else:
        current_thread = None

    new_thread = session.user.subreddit.submit(**post_details)
    new_thread.disable_inbox_replies()
    new_thread_mod = session.mod.reddit.submission(id=new_thread.id)
    new_thread_mod.mod.approve()

    # Unpin old thread and pin new one
    if thread_config["pin_thread"]:
        bottom_sticky = thread_config["pin_thread"] != "top"
        if current_thread:
            current_thread.mod.sticky(state=False)
            time.sleep(10)
        try:
            sticky_to_keep = session.mod.subreddit.sticky(number=1)
            if current_thread and sticky_to_keep.id == current_thread.id:
                sticky_to_keep = session.mod.subreddit.sticky(number=2)
        except prawcore.exceptions.NotFound:
            sticky_to_keep = None
        new_thread_mod.mod.sticky(state=True, bottom=bottom_sticky)
        if sticky_to_keep:
            sticky_to_keep.mod.sticky(state=True)

    # Update links to point to new thread
    if current_thread:
        links = [
            tuple([getattr(thread, link_type).strip("/")
                   for thread in [current_thread, new_thread]])
            for link_type in ["permalink", "shortlink"]]
        for page_name in thread_config["link_update_pages"]:
            page = create_sync_endpoint(
                endpoint_name=page_name,
                endpoint_type=EndpointType.WIKI_PAGE,
                subreddit=session.mod.subreddit,
                )
            for old_link, new_link in links:
                new_content = re.sub(
                    pattern=re.escape(old_link),
                    repl=new_link,
                    string=page.content,
                    flags=re.IGNORECASE,
                    )
            page.edit(new_content, reason="Update megathread URLs")

    # Update config accordingly
    dynamic_config["thread_id"] = new_thread.id


def manage_thread(session, thread_config, dynamic_config):
    """Manage the current thread, creating or updating it as necessary."""
    if not thread_config["enabled"]:
        return None
    thread_config = {**DEFAULT_MEGATHREAD_CONFIG, **thread_config}
    interval = thread_config["new_thread_interval"]

    source_timestamp = session.mod.subreddit.wiki[
        thread_config["source_name"]].revision_date
    wiki_updated = (source_timestamp > dynamic_config["source_timestamp"])

    current_thread = None
    last_post_timestamp = 0
    if dynamic_config["thread_id"]:
        current_thread = session.user.reddit.submission(
            id=dynamic_config["thread_id"])
        last_post_timestamp = datetime.datetime.fromtimestamp(
            current_thread.created_utc, tz=datetime.timezone.utc)
    current_datetime = datetime.datetime.now(datetime.timezone.utc)
    should_post_new_thread = not last_post_timestamp or (
        interval and (getattr(last_post_timestamp, interval)
                      != getattr(current_datetime, interval)))

    if wiki_updated or should_post_new_thread:
        if should_post_new_thread:
            create_new_thread(session, thread_config, dynamic_config)
        else:
            update_current_thread(session, thread_config, dynamic_config)
        dynamic_config["source_timestamp"] = source_timestamp
        return True
    return False


def manage_threads(session):
    """Check and create/update all defined megathreads for a sub."""
    for thread_id, thread_config in session.config["megathreads"].items():
        dynamic_config = session.dynamic_config["megathreads"][thread_id]
        manage_thread(
            session=session,
            thread_config=thread_config,
            dynamic_config=dynamic_config,
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


def sync_one(sync_pair, dynamic_config, reddit, subreddit):
    """Sync one specific pair of sources and targets."""
    sync_pair = {**DEFAULT_SYNC_PAIR, **sync_pair}
    description = sync_pair.get("description", "Unnamed")

    if not sync_pair["enabled"]:
        return None
    if not sync_pair["targets"]:
        raise ConfigError(
            f"No sync targets specified for sync_pair {description}")

    source_config = {**DEFAULT_SYNC_ENDPOINT, **sync_pair["source"]}
    if not source_config["enabled"]:
        return None

    source_obj = create_sync_endpoint_from_config(
        config=source_config, reddit=reddit, subreddit=subreddit)
    source_content = process_source_endpoint(
        source_config, source_obj, dynamic_config)
    if source_content is False:
        return False

    for target_config in sync_pair["targets"].values():
        target_config = {
            **DEFAULT_SYNC_ENDPOINT, **source_config, **target_config}
        if not target_config["enabled"]:
            continue

        target_obj = create_sync_endpoint_from_config(
            config=target_config, reddit=reddit, subreddit=subreddit)
        target_content = process_target_endpoint(
            target_config, target_obj, source_content)
        if target_content is False:
            continue

        target_obj.edit(
            target_content,
            reason=f"Auto-sync {description} from {target_obj.name}",
            )
    return True


def sync_all(session):
    """Sync all pairs of sources/targets (pages,threads, sections) on a sub."""
    for sync_pair_id, sync_pair in session.config["sync_pairs"].items():
        dynamic_config = session.dynamic_config["sync_pairs"][sync_pair_id]
        sync_one(
            sync_pair=sync_pair,
            dynamic_config=dynamic_config,
            reddit=session.mod.reddit,
            subreddit=session.mod.subreddit,
            )


# ----------------- Orchestration -----------------

def run_manage(
        config_path_static=CONFIG_PATH_STATIC,
        config_path_dynamic=CONFIG_PATH_DYNAMIC,
        ):
    """Load the config file and run the thread manager."""
    # Load config and set up session
    config = load_static_config(config_path_static)
    dynamic_config = load_dynamic_config(config_path_dynamic, config)
    session = MegathreadSession(
        static_config=config, dynamic_config=copy.deepcopy(dynamic_config))

    # Run the core manager tasks
    if session.config["sync_enabled"]:
        sync_all(session)
    if session.config["megathreads_enabled"]:
        manage_threads(session)

    # Write out the dynamic config if it changed
    if session.dynamic_config != dynamic_config:
        write_config(session.dynamic_config, config_path=config_path_dynamic)


def run_manage_loop(
        config_path_static=CONFIG_PATH_STATIC,
        config_path_dynamic=CONFIG_PATH_DYNAMIC,
        repeat=True,
        ):
    config = load_static_config(config_path=config_path_static)
    if repeat is True:
        repeat = config.get(
            "repeat_interval_s", DEFAULT_CONFIG["repeat_interval_s"])
    while True:
        print(f"Running megathread manager for config at {config_path_static}")
        run_manage(
            config_path_static=config_path_static,
            config_path_dynamic=config_path_dynamic,
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
