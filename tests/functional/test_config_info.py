"""Test that the get-config-info command works as expected."""

# Future imports
from __future__ import (
    annotations,
)

# Third party imports
import pytest
from typing_extensions import (
    Final,
)

# Local imports
import submanager.models.config
from tests.functional.conftest import (
    CONFIG_PATHS_ALL,
    DEBUG_ARGS,
    RunAndCheckCLICallable,
)

# ---- Constants ----

CONFIG_INFO_COMMAND: Final[str] = "get-config-info"
ENDPOINTS_ARGS: Final[list[str]] = ["", "--endpoints"]


# ---- Tests ----


@pytest.mark.parametrize("debug", DEBUG_ARGS)
@pytest.mark.parametrize("endpoints", ENDPOINTS_ARGS)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ALL, indirect=True)
def test_get_config_info(
    run_and_check_cli: RunAndCheckCLICallable,
    file_config: submanager.models.config.ConfigPaths,
    endpoints: str,
    debug: str,
) -> None:
    """Test that running the get-config-info command doesn't break."""
    run_and_check_cli(
        cli_args=[debug, CONFIG_INFO_COMMAND, endpoints],
        config_paths=file_config,
        check_text="endpoint" if endpoints else "path",
    )
