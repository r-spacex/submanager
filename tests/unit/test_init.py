"""Test that the package version and other initialization is valid."""

# Future imports
from __future__ import (
    annotations,
)

# Third party imports
import packaging.version
from typing_extensions import (
    Final,
)

# Local imports
import submanager

# ---- Constants ----

BASELINE_VERSION: Final[str] = "0.5.0"


# ---- Tests ----


def test_version() -> None:
    """Check that the package version exists and parses correctly."""
    version = submanager.__version__

    assert version
    assert isinstance(version, str)
    parsed_version = packaging.version.Version(version)
    assert parsed_version > packaging.version.Version(BASELINE_VERSION)
