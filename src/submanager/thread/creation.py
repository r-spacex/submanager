"""Perform the tasks necessary to create a new thread and deprecate the old."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import contextlib
import re
import time

# Third party imports
import praw.models.reddit.submission
import praw.reddit
import prawcore.exceptions
from typing_extensions import (
    Final,
    Literal,
)

# Local imports
import submanager.endpoint.creation
import submanager.endpoint.endpoints
import submanager.enums
import submanager.models.config
import submanager.sync.processing
import submanager.sync.utils
import submanager.thread.utils
import submanager.utils.output
from submanager.types import (
    AccountsMap,
    TemplateVars,
)

# ---- Constants ----

THREAD_ATTRIBUTES: Final[tuple[str, ...]] = (
    "id",
    "url",
    "permalink",
    "shortlink",
)


# ---- Helper classes ----


class ThreadAccountContext:
    """Stores the objects for a new and previous thread for one account."""

    def __init__(
        self,
        reddit: praw.reddit.Reddit,
        new_thread_id: str,
        current_thread_id: str | Literal[False] | None = None,
    ) -> None:
        self.reddit = reddit
        self.new_thread: praw.models.reddit.submission.Submission
        self.new_thread = self.reddit.submission(id=new_thread_id)

        self.current_thread: praw.models.reddit.submission.Submission | None
        self.current_thread = None
        if current_thread_id:
            self.current_thread = self.reddit.submission(id=current_thread_id)


class ThreadContext:
    """Stores the Reddit objects for the post and mod accounts."""

    def __init__(
        self,
        thread_config: submanager.models.config.ThreadItemConfig,
        accounts: AccountsMap,
        new_thread_id: str,
        current_thread_id: str | Literal[False] | None = None,
    ) -> None:
        self.post = ThreadAccountContext(
            reddit=accounts[thread_config.target_context.account],
            new_thread_id=new_thread_id,
            current_thread_id=current_thread_id,
        )
        self.mod = ThreadAccountContext(
            reddit=accounts[thread_config.context.account],
            new_thread_id=new_thread_id,
            current_thread_id=current_thread_id,
        )


# ---- Helper functions ----


def create_new_thread(
    thread_config: submanager.models.config.ThreadItemConfig,
    dynamic_config: submanager.models.config.DynamicThreadItemConfig,
    accounts: AccountsMap,
    template_vars: TemplateVars,
) -> praw.models.reddit.submission.Submission:
    """Create a new thread based on the title and post template."""
    # Create sync endpoint for source
    source_obj = submanager.endpoint.creation.create_sync_endpoint_from_config(
        config=thread_config.source,
        reddit=accounts[thread_config.source.context.account],
    )
    post_text = submanager.sync.processing.process_source_endpoint(
        thread_config.source,
        source_obj,
        dynamic_config,
    )
    pattern = submanager.sync.utils.PATTERN_TEMPLATE.format(
        pattern=f"{submanager.thread.utils.THREAD_PATTERN}{{suffix}}",
    )
    start_suffix = thread_config.source.pattern_start
    end_suffix = thread_config.source.pattern_end
    post_lines = [
        pattern.format(suffix=start_suffix),
        "",
        str(post_text).strip(),
        "",
        pattern.format(suffix=end_suffix),
    ]
    post_text = "\n".join(post_lines)
    new_thread: praw.models.reddit.submission.Submission = (
        accounts[thread_config.target_context.account]
        .subreddit(thread_config.target_context.subreddit)
        .submit(title=template_vars["post_title"], selftext=post_text)
    )
    new_thread.disable_inbox_replies()  # type: ignore[no-untyped-call]
    for attribute in THREAD_ATTRIBUTES:
        template_vars[f"thread_{attribute}"] = getattr(new_thread, attribute)

    return new_thread


def handle_pin_thread(
    pin_mode: submanager.enums.PinMode | bool,
    subreddit: str,
    thread_context_mod: ThreadAccountContext,
) -> bool | None:
    """Analyze the currently pinned thread and pin the new one correctly."""
    if not pin_mode or pin_mode is submanager.enums.PinMode.NONE:
        return None

    # Set up variables
    pin_to_keep: praw.models.reddit.submission.Submission | None = None
    subreddit_mod = thread_context_mod.reddit.subreddit(subreddit)
    auto = pin_mode is submanager.enums.PinMode.AUTO

    # Unpin previous thread if not in auto pin mode
    if not auto and thread_context_mod.current_thread:
        thread_context_mod.current_thread.mod.sticky(state=False)
        time.sleep(2)  # nosemgrep

    # Get currently pinned threads
    current_pins: list[praw.models.reddit.submission.Submission] = []
    for pin_n in range(1, 3):
        # Ignore if no pinned thread
        with contextlib.suppress(prawcore.exceptions.NotFound):
            current_pins.append(subreddit_mod.sticky(number=pin_n))

    # Get current pinned thread ids and determine current thread status
    pinned_thread_ids = [thread.id for thread in current_pins]
    current_thread_id = None
    if thread_context_mod.current_thread:
        current_thread_id = thread_context_mod.current_thread.id
    if auto:
        if not current_thread_id or current_thread_id not in pinned_thread_ids:
            return False
        bottom_pin = bool(pinned_thread_ids.index(current_thread_id))
    else:
        bottom_pin = pin_mode is not submanager.enums.PinMode.TOP
    if not bottom_pin and len(current_pins) > 1:
        pin_to_keep = current_pins[1]

    # Pin new thread, re-approving and retrying once if it fails
    try:
        thread_context_mod.new_thread.mod.sticky(state=True, bottom=bottom_pin)
    except prawcore.exceptions.BadRequest as error:
        print(  # noqa: WPS421
            f"Attempt to pin thread {thread_context_mod.new_thread.title!r} "
            "failed the first time due to an error; retrying. "
            "The error was:",
        )
        submanager.utils.output.print_error(error)
        thread_context_mod.new_thread.mod.approve()
        thread_context_mod.new_thread.mod.sticky(state=True, bottom=bottom_pin)

    if pin_to_keep:
        pin_to_keep.mod.sticky(state=True, bottom=True)

    return True


def update_page_links(
    thread_config: submanager.models.config.ThreadItemConfig,
    thread_context: ThreadContext,
) -> None:
    """Update the links to the given thread on the passed pages."""
    if not (
        thread_context.post.current_thread
        and thread_context.mod.current_thread
    ):
        return

    links = {
        getattr(thread_context.post.current_thread, link_type).strip("/"): (
            getattr(thread_context.post.new_thread, link_type).strip("/")
        )
        for link_type in ("permalink", "shortlink")
    }

    uid = thread_config.uid + ".link_update_pages"
    for page_name in thread_config.link_update_pages:
        page_config = submanager.models.config.EndpointConfig(
            context=thread_config.context,
            description=f"Thread link page {page_name}",
            endpoint_name=page_name,
            uid=uid + f".{page_name}",
        )
        page = submanager.endpoint.endpoints.WikiSyncEndpoint(
            config=page_config,
            reddit=thread_context.mod.reddit,
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
            new_content,
            reason=(
                f"Update {thread_config.description or thread_config.uid} "
                "thread URLs"
            ),
        )


def add_redirect_messages(
    thread_config: submanager.models.config.ThreadItemConfig,
    thread_context: ThreadContext,
    template_vars: TemplateVars,
) -> None:
    """Add a customizable redirect message to the old thread."""
    if not (
        thread_context.post.current_thread
        and thread_context.mod.current_thread
    ):
        return

    redirect_template = thread_config.redirect_template
    redirect_message = redirect_template.strip().format(**template_vars)

    if thread_config.redirect_op:
        current_text = thread_context.post.current_thread.selftext
        thread_context.post.current_thread.edit(
            f"{redirect_message}\n\n{current_text}",
        )
    if thread_config.redirect_sticky:
        redirect_comment = thread_context.mod.current_thread.reply(
            redirect_message,
        )
        redirect_comment.mod.distinguish(sticky=True)


# ---- Top-level functions ----


def handle_new_thread(
    thread_config: submanager.models.config.ThreadItemConfig,
    dynamic_config: submanager.models.config.DynamicThreadItemConfig,
    accounts: AccountsMap,
) -> None:
    """Handle creating and setting up a new thread and retiring the old."""
    # Bump counts in dynamic config
    dynamic_config.source_timestamp = 0
    dynamic_config.thread_number += 1

    # Generate template variables, title and post text and post
    template_vars = submanager.thread.utils.generate_template_vars(
        thread_config,
        dynamic_config,
    )
    new_thread = create_new_thread(
        thread_config=thread_config,
        dynamic_config=dynamic_config,
        accounts=accounts,
        template_vars=template_vars,
    )

    # Initialize thread context and approve thread
    thread_context = ThreadContext(
        thread_config=thread_config,
        accounts=accounts,
        new_thread_id=new_thread.id,
        current_thread_id=dynamic_config.thread_id,
    )
    if thread_config.approve_new:
        thread_context.mod.new_thread.mod.approve()

    # Unpin old thread and pin new one
    handle_pin_thread(  # static analysis: ignore[incompatible_argument]
        pin_mode=thread_config.pin_mode,
        subreddit=thread_config.context.subreddit,
        thread_context_mod=thread_context.mod,
    )

    # Update links to point to new thread
    update_page_links(
        thread_config=thread_config,
        thread_context=thread_context,
    )

    # Add messages to new thread on old thread if enabled
    add_redirect_messages(
        thread_config=thread_config,
        thread_context=thread_context,
        template_vars=template_vars,
    )

    # Update dynamic config accordingly
    dynamic_config.thread_id = thread_context.post.new_thread.id
