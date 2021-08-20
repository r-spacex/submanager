"""Test that the install-service command works as expected in the CLI."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import configparser
import sys
from pathlib import (
    Path,
)
from typing import (
    Callable,
)

# Third party imports
import pytest
from typing_extensions import (
    Final,
)

# Local imports
import submanager.enums
import submanager.exceptions
from tests.functional.conftest import (
    RunAndCheckCLICallable,
)

# ---- Types ----

CheckServiceCallable = Callable[[Path], None]


# ---- Constants ----

INSTALL_COMMAND: Final[str] = "install-service"
OUTPUT_DIR_ARG: Final[str] = "--output-dir"
FORCE_UNSUPPORTED_ARG: Final[str] = "--force-unsupported"

SUFFIX_ARGS: Final[list[str]] = ["", "test"]
FORCE_UNSUPPORTED_ARGS: Final[list[str]] = ["", FORCE_UNSUPPORTED_ARG]
OUTPUT_SUBDIR_ARGS: Final[list[str]] = ["", "missing_dir"]

OUTPUT_FILENAME_DEFAULT: Final[str] = "submanager.service"


# ---- Fixtures


@pytest.fixture(name="check_service")
def fixture_check_service() -> CheckServiceCallable:
    """Check that the service file conforms to the expected format."""

    def _check_service(output_path: Path) -> None:
        if output_path.suffix.lower() != ".service":
            output_path /= OUTPUT_FILENAME_DEFAULT

        assert output_path.exists()
        service_config = configparser.ConfigParser()
        assert service_config.read([output_path], encoding="utf-8")
        assert service_config.items()
        assert next(iter(service_config.items()))
        with open(output_path, encoding="utf-8", newline="\n") as service_file:
            service_text = service_file.read()
        assert service_text.strip()
        assert "\r" not in service_text
        assert "{" not in service_text
        assert "}" not in service_text

    return _check_service


# ---- Tests ----


@pytest.mark.parametrize("create_existing", [False, True])
@pytest.mark.parametrize("output_subdir", OUTPUT_SUBDIR_ARGS)
@pytest.mark.parametrize("suffix", SUFFIX_ARGS)
def test_install_service(
    run_and_check_cli: RunAndCheckCLICallable,
    check_service: CheckServiceCallable,
    tmp_path: Path,
    suffix: str,
    output_subdir: str,
    create_existing: bool,
) -> None:
    """Test that the service is installed correctly."""
    output_dir = tmp_path
    if output_subdir:
        output_dir /= output_subdir
    if create_existing:
        (tmp_path / OUTPUT_FILENAME_DEFAULT).touch(exist_ok=False)
    cli_args = [
        INSTALL_COMMAND,
        suffix,
        OUTPUT_DIR_ARG,
        output_dir.as_posix(),
        FORCE_UNSUPPORTED_ARG,
    ]

    run_and_check_cli(
        cli_args=cli_args,
        check_text="generat",
    )

    output_path = output_dir
    if suffix:
        output_path /= f"submanager-{suffix}.service"
    check_service(output_path)


def test_install_service_platform(
    run_and_check_cli: RunAndCheckCLICallable,
    check_service: CheckServiceCallable,
    tmp_path: Path,
) -> None:
    """Test that service install behaves as expected on the platform."""
    is_linux = sys.platform.startswith("linux")
    if is_linux:
        check_text = "generat"
        check_exits = False
    else:
        check_text = "support"
        check_exits = True

    cli_args = [
        INSTALL_COMMAND,
        OUTPUT_DIR_ARG,
        tmp_path.as_posix(),
    ]

    run_and_check_cli(
        cli_args=cli_args,
        check_text=check_text,
        check_exits=check_exits,
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.PlatformUnsupportedError,
    )

    if is_linux:
        check_service(tmp_path)
