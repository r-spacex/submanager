"""Package-level physical, path and general global constants."""

# Future imports
from __future__ import annotations

# Standard library imports
import time
from pathlib import Path

# Third party imports
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )

# Local imports
import submanager


# ---- General constants ----

USER_AGENT: Final[str] = (
    f"praw:submanager:v{submanager.__version__} (by u/CAM-Gerlach)")


# ---- Time constants ----

START_TIME: Final[float] = time.monotonic()


# ---- Path constants ----

CONFIG_DIRECTORY: Final[Path] = Path("~/.config/submanager").expanduser()
TOKEN_DIRECTORY: Final[Path] = CONFIG_DIRECTORY / "refresh_tokens"

CONFIG_PATH_STATIC: Final[Path] = CONFIG_DIRECTORY / "config.toml"
CONFIG_PATH_DYNAMIC: Final[Path] = CONFIG_DIRECTORY / "config_dynamic.json"
CONFIG_PATH_REFRESH: Final[Path] = TOKEN_DIRECTORY / "refresh_token_{key}.txt"


# ---- URL constants ----

REDDIT_BASE_URL: Final[str] = "https://www.reddit.com"
