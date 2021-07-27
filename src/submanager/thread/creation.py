"""Perform the tasks nessesary to create a new thread and deprecate the old."""

# Future imports
from __future__ import annotations

# Standard library imports
import re
import time
from typing import (
    Collection,  # Import from collections.abc in Python 3.9
    Mapping,  # Import from collections.abc in Python 3.9
    )

# Third party imports
import praw.models.reddit.submission
import praw.reddit
import prawcore.exceptions

# Local imports
import submanager.endpoint.creation
import submanager.endpoint.endpoints
import submanager.enums
import submanager.exceptions
import submanager.models.config
import submanager.sync.processing
import submanager.thread.utils
from submanager.types import (
    AccountsMap,
    )


def update_page_links(
        links: Mapping[str, str],
        pages_to_update: Collection[str],
        reddit: praw.reddit.Reddit,
        *,
        context: submanager.models.config.ContextConfig,
        uid: str,
        description: str = "",
        ) -> None:
    """Update the links to the given thread on the passed pages."""
    uid_base = ".".join(uid.split(".")[:-1])
    for page_name in pages_to_update:
        page_config = submanager.models.config.EndpointConfig(
            context=context,
            description=f"Thread link page {page_name}",
            endpoint_name=page_name,
            uid=uid + f".{page_name}",
            )
        page = submanager.endpoint.endpoints.WikiSyncEndpoint(
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
                f"Update {description or uid_base} thread URLs"))


def create_new_thread(
        thread_config: submanager.models.config.ThreadItemConfig,
        dynamic_config: submanager.models.config.DynamicThreadItemConfig,
        accounts: AccountsMap,
        ) -> None:
    """Create a new thread based on the title and post template."""
    # Generate thread title and contents
    dynamic_config.source_timestamp = 0
    dynamic_config.thread_number += 1

    # Get subreddit objects for accounts
    reddit_mod = accounts[thread_config.context.account]
    reddit_post = accounts[thread_config.target_context.account]

    # Create sync endpoint for source
    source_obj = submanager.endpoint.creation.create_sync_endpoint_from_config(
        config=thread_config.source,
        reddit=accounts[thread_config.source.context.account])

    # Generate template variables, title and post text
    template_vars = submanager.thread.utils.generate_template_vars(
        thread_config, dynamic_config)
    post_text = submanager.sync.processing.process_source_endpoint(
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
    for attribute in ("id", "url", "permalink", "shortlink"):
        template_vars[f"thread_{attribute}"] = getattr(new_thread, attribute)

    # Unpin old thread and pin new one
    if thread_config.pin_thread and (
            thread_config.pin_thread is not submanager.enums.PinType.NONE):
        bottom_sticky = (
            thread_config.pin_thread is not submanager.enums.PinType.TOP)
        if current_thread_mod:
            current_thread_mod.mod.sticky(state=False)
            time.sleep(10)
        sticky_to_keep: praw.models.reddit.submission.Submission | None = None
        try:
            sticky_to_keep = reddit_mod.subreddit(
                thread_config.context.subreddit).sticky(number=1)
        except prawcore.exceptions.NotFound:  # Ignore if no sticky
            pass
        if (current_thread and sticky_to_keep
                and sticky_to_keep.id == current_thread.id):
            try:
                sticky_to_keep = reddit_mod.subreddit(
                    thread_config.context.subreddit).sticky(number=2)
            except prawcore.exceptions.NotFound:  # Ignore if no sticky
                pass
        new_thread_mod.mod.sticky(state=True, bottom=bottom_sticky)
        if sticky_to_keep:
            sticky_to_keep.mod.sticky(state=True)

    if current_thread and current_thread_mod:
        # Update links to point to new thread
        links = {
            getattr(current_thread, link_type).strip("/"): (
                getattr(new_thread, link_type).strip("/"))
            for link_type in ("permalink", "shortlink")}
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

    # Update dynamic config accordingly
    dynamic_config.thread_id = new_thread.id
