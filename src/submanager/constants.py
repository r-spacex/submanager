"""Package-level physical, path and general global constants."""

# Future imports
from __future__ import annotations

# Standard library imports
import time
from pathlib import Path

# Third party imports
import platformdirs
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )

# Local imports
import submanager


# ---- General constants ----

PACKAGE_NAME: Final[str] = "submanager"

USER_AGENT: Final[str] = (
    f"praw:{PACKAGE_NAME}:v{submanager.__version__} (by u/CAM-Gerlach)")


# ---- Time constants ----

START_TIME: Final[float] = time.monotonic()


# ---- Path constants ----

USER_CONFIG_DIR: Final[Path] = platformdirs.user_config_path(
    appname=PACKAGE_NAME, appauthor=PACKAGE_NAME, roaming=True)
USER_STATE_DIR: Final[Path] = platformdirs.user_state_path(
    appname=PACKAGE_NAME, appauthor=PACKAGE_NAME, roaming=True)

CONFIG_PATH_STATIC: Final[Path] = USER_CONFIG_DIR / "config.toml"
CONFIG_PATH_DYNAMIC: Final[Path] = USER_STATE_DIR / "config_dynamic.json"


# ---- URL constants ----

REDDIT_BASE_URL: Final[str] = "https://www.reddit.com"
