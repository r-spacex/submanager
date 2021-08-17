"""Common top-level test fixtures."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
from pathlib import (
    Path,
)
from typing import (
    Collection,
    Mapping,
)

# Third party imports
import pytest
from _pytest.config import (  # noqa: WPS436
    Config,
)
from _pytest.config.argparsing import (  # noqa: WPS436
    Parser,
)
from typing_extensions import (
    Final,
)

# ---- Constants ----

PACKAGE_NAME: Final[str] = "submanager"

RUN_ONLINE_OPTION: Final[str] = "--run-online"


# ---- Helpers ----


def _get_val_id_from_collection(
    val: Collection[object],  # noqa: WPS110
) -> str | object:
    """Extract a suitible test ID string from a collection, if possible."""
    if isinstance(val, Mapping):
        # static analysis: ignore[undefined_attribute]
        val_iter = iter(val.values())
    else:
        val_iter = iter(val)
    if len(val) == 1:
        val_id: object = next(val_iter)
        return val_id
    if all(isinstance(val_item, str) for val_item in val):
        # static analysis: ignore[incompatible_argument]
        return " ".join(val)  # type: ignore[arg-type]

    return val


def _get_val_id(val: object) -> str | object:  # noqa: WPS110
    """Get the ID string from an arbitrary test param object, if possible."""
    val_name: object = getattr(val, "name", None)
    if isinstance(val, Path):
        return val.stem
    # static analysis: ignore[non_boolean_in_boolean_context]
    if val_name and isinstance(val_name, str):
        return val_name
    if isinstance(val, Collection):
        # static analysis: ignore[incompatible_argument]
        return _get_val_id_from_collection(val)

    return val


# ---- Hooks ----


def pytest_addoption(parser: Parser) -> None:
    """Add an option to run online tests to the pytest argument parser."""
    parser.addoption(
        RUN_ONLINE_OPTION,
        action="store_true",
        default=False,
        help="Run tests that require interacting with live Reddit",
    )


def pytest_collection_modifyitems(
    config: Config, items: list[pytest.Item]
) -> None:
    """Ensure that online tests are skipped unless run online is passed."""
    if not config.getoption(RUN_ONLINE_OPTION):
        skip_online = pytest.mark.skip(reason="Needs --run-online")
        for item in items:
            if "online" in item.keywords:
                item.add_marker(skip_online)


def pytest_make_parametrize_id(val: object) -> str | None:  # noqa: WPS110
    """Intelligently generate parameter IDs; hook for pytest."""
    val_id: object
    if isinstance(val, (str, bytes)):
        val_id = val
    else:
        val_id = _get_val_id(val)

    if isinstance(val_id, bytes):
        return val_id.decode()
    if isinstance(val_id, str):
        return val_id.strip().strip("-").replace("-", "")
    if val_id is None or isinstance(val_id, (int, float, complex, bool)):
        return str(val_id)

    return None
