"""Test that basic CLI usage is handled properly."""

# Future imports
from __future__ import annotations

# Standard library imports
from typing import (
    Callable,  # Import from collections.abc in Python 3.9
    Optional,  # Not needed in Python 3.10
    Sequence,  # Not needed in Python 3.9
    Tuple,  # Not needed in Python 3.9
    )

# Third party imports
import pytest
from _pytest.capture import (
    CaptureResult,
    )

# Local imports
import submanager.enums


# ---- Types ----

RunCLIOutput = Tuple[CaptureResult[str], Optional[SystemExit]]
RunCLICallable = Callable[[Sequence[str]], RunCLIOutput]


# ---- Tests ----

@pytest.mark.parametrize(
    "cli_args", [["-h"], ["--help"]], ids=["short", "long"])
def test_help_usage(
        run_cli: RunCLICallable,
        cli_args: list[str],
        ) -> None:
    """Test that the program prints help when --help is passed."""
    captured_output, captured_error = run_cli(cli_args)

    assert captured_error
    assert not captured_error.code
    assert captured_error.code == submanager.enums.ExitCode.SUCCESS.value
    assert ("help" in captured_output.out.lower()
            or "help" in captured_output.err.lower())


@pytest.mark.parametrize(
    "cli_args", [["--version"]], ids=["version"])
def test_good_usage(
        run_cli: RunCLICallable,
        cli_args: list[str],
        ) -> None:
    """Test that the program performs properly when correct args are passed."""
    captured_output, captured_error = run_cli(cli_args)

    assert not captured_error
    assert cli_args[0].replace("-", "").strip() in captured_output.out.lower()
    assert not captured_output.err.strip()


@pytest.mark.parametrize(
    "cli_args", [[""], ["--non-existant-flag"]], ids=["empty", "non-existant"])
def test_bad_usage(
        run_cli: RunCLICallable,
        cli_args: list[str],
        ) -> None:
    """Test that the program prints usage when invoked with no args."""
    captured_output, captured_error = run_cli(cli_args)

    assert captured_error
    assert (captured_error.code and captured_error.code
            == submanager.enums.ExitCode.ERROR_PARAMETERS.value)
    assert "usage" in captured_output.err.lower()
    assert not captured_output.out.strip()
