"""Subreddit menu parsing and generation."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
# Standard libraryu imports
import re

# Third party imports
from typing_extensions import (
    Literal,
)

# Local imports
import submanager.models.config
from submanager.types import (
    ChildrenData,
    MenuData,
    SectionData,
)

# ---- Text processing utilities ----


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


def parse_section(
    menu_section: str,
    menu_config: submanager.models.config.MenuConfig,
) -> SectionData:
    """Construct the data for each menu section in the source."""
    menu_subsections = split_and_clean_text(menu_section, menu_config.subsplit)

    # Skip if no title or menu items, otherwise add the title
    if not menu_subsections:
        return {}
    title_text = extract_text(menu_config.pattern_title, menu_subsections[0])
    if title_text is False:
        return {}
    section_data: SectionData = {"text": title_text}

    # If menu is a singular item, just add that
    if len(menu_subsections) == 1:
        url_text = extract_text(menu_config.pattern_url, menu_subsections[0])
        if url_text is False:
            return {}
        section_data["url"] = url_text
    # Otherwise, process each of the child menu items
    else:
        children: ChildrenData = []
        for menu_child in menu_subsections[1:]:
            title_text = extract_text(menu_config.pattern_subtitle, menu_child)
            url_text = extract_text(menu_config.pattern_url, menu_child)
            if title_text is not False and url_text is not False:
                children.append({"text": title_text, "url": url_text})
        section_data["children"] = children

    return section_data


def parse_menu(
    source_text: str,
    menu_config: submanager.models.config.MenuConfig | None = None,
) -> MenuData:
    """Parse source Markdown text and render it into a strucured format."""
    if menu_config is None:
        menu_config = submanager.models.config.MenuConfig()

    # Cleanup menu source text
    menu_data = []
    source_text = source_text.replace("\r\n", "\n")
    menu_sections = split_and_clean_text(source_text, menu_config.split)

    for menu_section in menu_sections:
        section_data = parse_section(menu_section, menu_config)
        if section_data:
            menu_data.append(section_data)

    return MenuData(menu_data)
