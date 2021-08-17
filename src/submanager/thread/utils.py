"""Utilities for creating and syncing threads."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import datetime

# Third party imports
import dateutil.relativedelta
import praw.models.reddit.submission
import praw.reddit
from typing_extensions import (
    Final,
)

# Local imports
import submanager.models.config
import submanager.models.utils
from submanager.types import (
    TemplateVars,
)

THREAD_PATTERN: Final[str] = "Auto Sync"


def generate_template_vars(
    thread_config: submanager.models.config.ThreadItemConfig,
    dynamic_config: submanager.models.config.DynamicThreadItemConfig,
) -> TemplateVars:
    """Generate the title and post templates."""
    thread_id_previous = (
        "" if not dynamic_config.thread_id else dynamic_config.thread_id
    )
    template_vars: TemplateVars = {
        "current_datetime": datetime.datetime.now(datetime.timezone.utc),
        "current_datetime_local": datetime.datetime.now(),
        "subreddit": thread_config.context.subreddit,
        "thread_number": dynamic_config.thread_number,
        "thread_number_previous": dynamic_config.thread_number - 1,
        "thread_id_previous": thread_id_previous,
    }
    template_vars["post_title"] = thread_config.post_title_template.format(
        **template_vars,
    )
    return template_vars


def should_post_new_thread(
    thread_config: submanager.models.config.ThreadItemConfig,
    dynamic_config: submanager.models.config.DynamicThreadItemConfig,
    reddit: praw.reddit.Reddit,
) -> bool:
    """Determine if a new thread should be posted."""
    # Don't create a new thread if disabled, otherwise always create if no prev
    if not thread_config.new_thread_interval:
        return False
    if not dynamic_config.thread_id:
        return True

    # Process the interval and the current thread
    interval_unit, interval_n = submanager.models.utils.process_raw_interval(
        thread_config.new_thread_interval,
    )
    current_thread: praw.models.reddit.submission.Submission = (
        reddit.submission(id=dynamic_config.thread_id)
    )

    # Get last post and current timestamp
    last_post_timestamp = datetime.datetime.fromtimestamp(
        current_thread.created_utc,
        tz=datetime.timezone.utc,
    )
    current_datetime = datetime.datetime.now(datetime.timezone.utc)

    # If fixed unit interval, simply compare equality, otherwise compare delta
    if interval_n is None:
        previous_n: int = getattr(last_post_timestamp, interval_unit)
        current_n: int = getattr(current_datetime, interval_unit)
        interval_exceeded = previous_n != current_n
    else:
        delta_kwargs: dict[str, int] = {f"{interval_unit}s": interval_n}
        relative_timedelta = dateutil.relativedelta.relativedelta(
            **delta_kwargs,  # type: ignore[arg-type]
        )
        interval_exceeded = current_datetime > (
            last_post_timestamp + relative_timedelta
        )

    return interval_exceeded
