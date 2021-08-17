"""Utilities to match patterns, clean up text and prepare it for syncing."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import re
from typing import (
    Mapping,
)

# Third party imports
from typing_extensions import (
    Final,
    Literal,
)

PATTERN_TEMPLATE: Final[str] = "[](/# {pattern})"


def truncate_lines(text: str, lines: int | Literal[False]) -> str:
    """Truncate the text to the specified number of lines."""
    if not lines:
        return text
    if lines < 0:
        raise ValueError(f"Lines to truncate must be > 0, not {lines!r}")
    return "\n".join(text.splitlines()[:lines])


def replace_patterns(text: str, patterns: Mapping[str, str]) -> str:
    """Replace each pattern in the text with its mapped replacement."""
    for old, new in patterns.items():
        text = text.replace(old, new)
    return text


def startend_to_pattern(start: str, end: str | None = None) -> str:
    """Convert a start and end string to capture everything between."""
    end = start if end is None else end
    pattern = r"(?<={start})(\s|\S)*(?={end})".format(
        start=re.escape(start),
        end=re.escape(end),
    )
    return pattern


def startend_to_pattern_md(start: str, end: str | None = None) -> str:
    """Convert start/end strings to a Markdown-"comment" capture pattern."""
    end = start if end is None else end
    start, end = (
        PATTERN_TEMPLATE.format(pattern=pattern) for pattern in (start, end)
    )
    return startend_to_pattern(start, end)


def pattern_to_pattern_md(pattern: str, start: str = "", end: str = "") -> str:
    """Convert a pattern to its Markdown equivalent."""
    start = pattern + start
    end = pattern + end
    return startend_to_pattern_md(start, end)


def search_startend(
    source_text: str,
    pattern: str | Literal[False] | None = "",
    start: str = "",
    end: str = "",
) -> re.Match[str] | Literal[False] | None:
    """Match the text between the given Markdown pattern w/suffices."""
    if pattern is False or pattern is None or not (pattern or start or end):
        return False
    pattern = pattern_to_pattern_md(pattern, start, end)
    match_obj = re.search(pattern, source_text)
    return match_obj
