#!/usr/bin/env python3
"""Main-level Sub Manager entry point."""

# Future imports
from __future__ import (
    annotations,
)

# Local imports
import submanager.cli


def main() -> None:
    """Run Sub Manager though the CLI."""
    submanager.cli.main()


if __name__ == "__main__":
    main()
