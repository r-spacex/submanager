#!/usr/bin/env python3
"""
Generate, pin and update a regular megathread for a subreddit.
"""

# Standard library imports
import argparse
import copy
import datetime
import json
from pathlib import Path
import re
import time

# Third party imports
import praw
import prawcore.exceptions


# ----------------- Constants -----------------

__version__ = "0.3.0dev0"

# General constants
CONFIG_DIRECTORY = Path("~/.config/megathread-manager").expanduser()
CONFIG_PATH_STATIC = CONFIG_DIRECTORY / "config.json"
CONFIG_PATH_DYNAMIC = CONFIG_DIRECTORY / "config_dynamic.json"
USER_AGENT = f"praw:megathreadmanager:v{__version__} (by u/CAM-Gerlach)"

# Config
DEFAULT_SYNC_ENDPOINT = {
    "description": "",
    "enabled": True,
    "pattern": "",
    "pattern_end": " End",
    "pattern_start": " Start",
    "replace_patterns": {},
    }

DEFAULT_SYNC_PAIR = {
    "description": "",
    "enabled": True,
    "source": {},
    "targets": [],
    }

DEFAULT_MEGATHREAD_CONFIG = {
    "description": "",
    "enabled": True,
    "initial": {
        "thread_number": 0,
        "thread_url": "",
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
        "thread_url": "",
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
        "primary": {
            "description": "Primary megathread",
            "enabled": False,
            "initial": {
                "thread_number": 0,
                "thread_url": "",
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
        "sidebar": {
            "description": "Sync Sidebar Demo",
            "source": {
                "description": "Thread source wiki page",
                "enabled": False,
                "name": "threads",
                "pattern": "Sidebar",
                "pattern_end": " End",
                "pattern_start": " Start",
                "replace_patterns": {
                    "https://www.reddit.com": "https://old.reddit.com",
                    },
                },
            "targets": [
                {
                    "description": "Sub Sidebar",
                    "enabled": True,
                    "name": "config/sidebar",
                    "pattern": "Sidebar",
                    "pattern_end": " Start",
                    "pattern_start": " End",
                    "replace_patterns": {},
                    },
                ],
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
    if not pattern or not (start and end):
        return False
    start = pattern + start
    end = pattern + end
    pattern = startend_to_pattern_md(start, end)
    match_obj = re.search(pattern, source_text)
    return match_obj


def get_item(subreddit, item):
    item_object = subreddit.wiki[item["name"]]
    item_text = item_object.content_md
    return item_object, item_text


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


# ----------------- Config functions -----------------

def write_config(config, config_path=CONFIG_PATH_DYNAMIC):
    """Write the passed config to the specified config path."""
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, mode="w",
              encoding="utf-8", newline="\n") as config_file:
        json.dump(config, config_file, indent=4)


def load_config(config_path):
    """Load the config file at the specified path."""
    with open(config_path, mode="r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    return config


def load_static_config(config_path=CONFIG_PATH_STATIC):
    """Load manager's static (user) config file, creating it if needed."""
    if not Path(config_path).exists():
        write_config(DEFAULT_CONFIG, config_path=config_path)
    static_config = load_config(config_path)
    static_config = {**DEFAULT_CONFIG, **static_config}
    if not static_config or static_config == DEFAULT_CONFIG:
        raise ConfigError(f"Config file at {config_path} needs to be set up.")
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
        "thread_url": dynamic_config["thread_url"],
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
        url=dynamic_config["thread_url"])
    current_thread.edit(post_details["selftext"])


def create_new_thread(session, thread_config, dynamic_config):
    """Create a new thread based on the title and post template."""
    dynamic_config["thread_number"] += 1
    post_details = generate_post_details(
        session, thread_config, dynamic_config)

    # Submit and approve new thread
    thread_url = dynamic_config["thread_url"]
    if thread_url:
        current_thread = session.user.reddit.submission(url=thread_url)
    else:
        current_thread = None

    new_thread = session.user.subreddit.submit(**post_details)
    new_thread.disable_inbox_replies()
    new_thread_mod = session.mod.reddit.submission(url=new_thread.url)
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
            page, page_content = get_item(
                session.mod.subreddit, {"name": page_name})
            for old_link, new_link in links:
                page_content = re.sub(
                    pattern=re.escape(old_link),
                    repl=new_link,
                    string=page_content,
                    flags=re.IGNORECASE,
                    )
            page.edit(page_content, reason="Update megathread URLs")

    # Update config accordingly
    dynamic_config["thread_url"] = new_thread.url


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
    if dynamic_config["thread_url"]:
        current_thread = session.user.reddit.submission(
            url=dynamic_config["thread_url"])
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

def sync_one(sync_pair, dynamic_config, subreddit):
    """Sync one specific pair of sources and targets."""
    sync_pair = {**DEFAULT_SYNC_PAIR, **sync_pair}
    description = sync_pair.get("description", "Unnamed")

    if not sync_pair["enabled"]:
        return None
    if not sync_pair["targets"]:
        raise ConfigError(
            f"No sync targets specified for sync_pair {description}")

    source = {**DEFAULT_SYNC_ENDPOINT, **sync_pair["source"]}
    if not source["enabled"]:
        return None

    source_page, source_text = get_item(subreddit, source)
    source_description = (
        source["description"] if source["description"] else source["name"])

    source_updated = (
        source_page.revision_date > dynamic_config["source_timestamp"])
    if not source_updated:
        return False
    dynamic_config["source_timestamp"] = source_page.revision_date

    match_obj = search_startend(
        source_text, source["pattern"],
        source["pattern_start"], source["pattern_end"])
    if match_obj is not False:
        if not match_obj:
            print(f"Sync pair {description} pattern not found in "
                  f"source {source_description}; skipping")
            return False
        source_text = match_obj.group()
    source_text = replace_patterns(source_text, source["replace_patterns"])

    for target in sync_pair["targets"]:
        target = {**DEFAULT_SYNC_ENDPOINT, **source, **target}
        if not target["enabled"]:
            continue
        target_page, target_text = get_item(subreddit, target)
        target_description = (
            target["description"] if target["description"] else target["name"])
        source_text_target = replace_patterns(
            source_text, target["replace_patterns"])
        match_obj = search_startend(
            target_text, target["pattern"],
            target["pattern_start"], target["pattern_end"])
        if match_obj is not False:
            if not match_obj:
                print(f"Sync pair {description} pattern not found in "
                      f"target {target_description}; skipping")
                return False

            target_text = re.sub(
                match_obj.re.pattern, source_text_target, target_text)
        else:
            target_text = source_text_target
        target_page.edit(
            target_text,
            reason=f"Auto-sync {description} from {source_page.name}")
    return True


def sync_all(session):
    """Sync all pairs of sources/targets (pages,threads, sections) on a sub."""
    for sync_pair_id, sync_pair in session.config["sync_pairs"].items():
        dynamic_config = session.dynamic_config["sync_pairs"][sync_pair_id]
        sync_one(
            sync_pair=sync_pair,
            dynamic_config=dynamic_config,
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
