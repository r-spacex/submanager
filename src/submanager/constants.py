"""Package-level physical, path and general global constants."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import time
from pathlib import (
    Path,
)

# Third party imports
import platformdirs
from typing_extensions import (
    Final,
)

# Local imports
import submanager

# ---- General constants ----

PACKAGE_NAME: Final[str] = "submanager"

LINE_LENGTH: Final[int] = 70
USER_AGENT: Final[
    str
] = f"praw:{PACKAGE_NAME}:v{submanager.__version__} (by u/CAM-Gerlach)"


# ---- Time constants ----

START_TIME: Final[float] = time.monotonic()


# ---- Path constants ----

SECURE_DIR_MODE: Final[int] = 0o770
SECURE_FILE_MODE: Final[int] = 0o660

USER_CONFIG_DIR: Final[Path] = platformdirs.user_config_path(
    appname=PACKAGE_NAME,
    appauthor=PACKAGE_NAME,
    roaming=True,
)
USER_STATE_DIR: Final[Path] = platformdirs.user_state_path(
    appname=PACKAGE_NAME,
    appauthor=PACKAGE_NAME,
    roaming=True,
)

CONFIG_PATH_STATIC: Final[Path] = USER_CONFIG_DIR / "config.toml"
CONFIG_PATH_DYNAMIC: Final[Path] = USER_STATE_DIR / "config_dynamic.json"


# ---- URL constants ----

REDDIT_BASE_URL: Final[str] = "https://www.reddit.com"
