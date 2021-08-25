"""Text processing services to prepare source text for syncing to target."""

# Future imports
from __future__ import (
    annotations,
)

# Third party imports
from typing_extensions import (
    Literal,
)

# Local imports
import submanager.endpoint.base
import submanager.endpoint.endpoints
import submanager.models.config
import submanager.sync.menu
import submanager.sync.utils
from submanager.types import (
    MenuData,
)


def process_source_text(
    source_text: str,
    endpoint_config: submanager.models.config.FullEndpointConfig,
) -> str:
    """Perform text processing operations on the source text."""
    source_text = submanager.sync.utils.replace_patterns(
        source_text,
        endpoint_config.replace_patterns,
    )
    source_text = submanager.sync.utils.truncate_lines(
        source_text,
        endpoint_config.truncate_lines,
    )
    return source_text


def handle_endpoint_pattern(
    content: str,
    pattern_config: submanager.models.config.PatternConfig,
    replace_text: str | None = None,
) -> str | Literal[False]:
    """Perform the desired find-replace for a specific sync endpoint."""
    match_obj = submanager.sync.utils.search_startend(
        content,
        pattern_config.pattern,
        pattern_config.pattern_start,
        pattern_config.pattern_end,
    )

    # If matched against a block in the endpoint, handle the match obj
    if match_obj is not False:
        # If the match obj was not found, return immediately
        if not match_obj:
            return False
        # Otherwise, process the comment-marked portion of the content
        output_text = match_obj.group()
        if replace_text is not None:
            output_text = content.replace(output_text, replace_text)
        return output_text

    # Otherwise, replace the current target content with the source
    output_text = content if replace_text is None else replace_text
    return output_text


def process_source_endpoint(
    source_config: submanager.models.config.FullEndpointConfig,
    source_obj: submanager.endpoint.base.SyncEndpoint,
    dynamic_config: submanager.models.config.DynamicSyncItemConfig,
) -> str | MenuData | Literal[False]:
    """Get and preprocess the text from a source if its out of date."""
    # If source has revision date, check it and skip if unchanged
    if isinstance(source_obj, submanager.endpoint.base.RevisionDateCheckable):
        source_timestamp = source_obj.revision_date
        source_updated = source_timestamp > dynamic_config.source_timestamp
        if not source_updated:
            return False
        dynamic_config.source_timestamp = source_timestamp

    # Otherwise, process the source text
    source_content = source_obj.content
    if isinstance(source_content, str):
        source_content_subset = handle_endpoint_pattern(
            source_content,
            source_config,
        )
        if source_content_subset is False:
            print(  # noqa: WPS421
                "Skipping sync pattern not found in source "
                f"{source_obj.config.description} {source_obj.config.uid}",
            )
            return False
        source_content_processed = process_source_text(
            source_content_subset,
            source_config,
        )
        return source_content_processed

    return source_content


def process_target_endpoint(
    target_config: submanager.models.config.FullEndpointConfig,
    target_obj: submanager.endpoint.base.SyncEndpoint,
    source_content: str | MenuData,
    menu_config: submanager.models.config.MenuConfig | None = None,
) -> str | MenuData | Literal[False]:
    """Handle text conversions and deployment onto a sync target."""
    # Perform the target-specific pattern replacements
    if isinstance(source_content, str):
        source_content = process_source_text(source_content, target_config)
        source_content = f"\n\n{source_content.strip()}\n\n"

    # If the target is a menu, build the source into one if not already one
    target_content = target_obj.content
    if isinstance(target_obj, submanager.endpoint.endpoints.MenuSyncEndpoint):
        if isinstance(source_content, str):
            target_content = submanager.sync.menu.parse_menu(
                source_text=source_content,
                menu_config=menu_config,
            )
        else:
            target_content = source_content
    # If they're both text, process the replacements
    elif isinstance(source_content, str) and isinstance(target_content, str):
        target_content_processed = handle_endpoint_pattern(
            target_content,
            target_config,
            replace_text=source_content,
        )
        if target_content_processed is False:
            print(  # noqa: WPS421
                "Skipping sync pattern not found in target "
                f"{target_obj.config.description} {target_obj.config.uid}",
            )
            return False
        return target_content_processed

    return target_content
