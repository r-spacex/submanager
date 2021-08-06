#!/usr/bin/env python3
"""Main-level command handling for running on the command line."""

# Future imports
from __future__ import annotations

# Standard library imports
import argparse
import sys
from pathlib import Path
from typing import (
    Any,
    Callable,  # Import from collections.abc in Python 3.9
    Sequence,  # Import from collections.abc in Python 3.9
    )

# Local imports
import submanager
import submanager.core.commands
import submanager.core.run
import submanager.enums
import submanager.exceptions
import submanager.models.config
import submanager.utils.output
from submanager.constants import (
    CONFIG_PATH_DYNAMIC,
    CONFIG_PATH_STATIC,
    )
from submanager.types import (
    PathLikeStr,
    )


def get_version_string() -> str:
    """Get a pretty-printed string of the package's version."""
    return f"Sub Manager version {submanager.__version__}"


def print_version_string() -> None:
    """Print the package's version string."""
    print(get_version_string())


def create_arg_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser_main = argparse.ArgumentParser(
        description=(
            "Manage subreddit threads, wiki pages, widgets, menus and more"),
        argument_default=argparse.SUPPRESS)
    subparsers = parser_main.add_subparsers(
        description="Subcommand to execute")

    # Top-level arguments
    parser_main.add_argument(
        "--version",
        action="store_true",
        help="Print the version number and exit",
        )
    parser_main.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Print full debug output instead of just user-friendly text",
        )
    parser_main.add_argument(
        "--config-path",
        dest="config_path_static",
        help="The path to a custom static (user) config file to use",
        )
    parser_main.add_argument(
        "--dynamic-config-path",
        dest="config_path_dynamic",
        help="The path to a custom dynamic (runtime) config file to use",
        )

    # Generate the config file
    generate_desc = "Generate the bot's config files"
    parser_generate = subparsers.add_parser(
        "generate-config",
        description=generate_desc,
        help=generate_desc,
        argument_default=argparse.SUPPRESS,
        )
    parser_generate.set_defaults(
        func=submanager.core.commands.run_generate_config)
    parser_generate.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the existing static config with the default example",
        )
    parser_generate.add_argument(
        "--exist-ok",
        action="store_true",
        help="Don't raise an error/warning if the config file already exists",
        )

    # Validate the config file
    validate_desc = "Validate the bot's config files"
    parser_validate = subparsers.add_parser(
        "validate-config",
        description=validate_desc,
        help=validate_desc,
        argument_default=argparse.SUPPRESS,
        )
    parser_validate.set_defaults(
        func=submanager.core.commands.run_validate_config)
    parser_validate.add_argument(
        "--offline-only",
        action="store_true",
        help="Only validate the config locally; don't call out to Reddit",
        )
    parser_validate.add_argument(
        "--minimal",
        action="store_true",
        help="Only perform the checks absolutely required for startup",
        )
    parser_validate.add_argument(
        "--include-disabled",
        action="store_true",
        help="Validate disabled modules and endpoints as well as enabled ones",
        )

    # Run the bot once
    run_desc = "Run the bot through one cycle and exit"
    parser_run = subparsers.add_parser(
        "run",
        description=run_desc,
        help=run_desc,
        argument_default=argparse.SUPPRESS,
        )
    parser_run.set_defaults(func=submanager.core.run.run_manage)
    parser_run.add_argument(
        "--skip-validate",
        action="store_true",
        help="Don't validate the config against Reddit prior to executing it",
        )

    # Start the bot running
    start_desc = "Start the bot running continously until stopped or errored"
    parser_start = subparsers.add_parser(
        "start",
        description=start_desc,
        help=start_desc,
        argument_default=argparse.SUPPRESS,
        )
    parser_start.set_defaults(func=submanager.core.run.start_manage)
    parser_start.add_argument(
        "--skip-validate",
        action="store_true",
        help="Don't validate the config against Reddit prior to executing it",
        )
    parser_start.add_argument(
        "--repeat-interval-s",
        type=float,
        metavar="SECONDS",
        help=("Run every SECONDS seconds; if not passed, uses the value "
              "variable repeat_interval_s from the config file"),
        )
    parser_start.add_argument(
        "--repeat-max-n",
        type=int,
        metavar="N",
        help="If passed, run only N times; useful for testing and debugging",
        )

    return parser_main


def run_toplevel_function(
        func: Callable[..., None],
        *,
        config_path_static: PathLikeStr = CONFIG_PATH_STATIC,
        config_path_dynamic: PathLikeStr = CONFIG_PATH_DYNAMIC,
        **kwargs: Any,
        ) -> None:
    """Dispatch to the top-level function, converting paths to objs."""
    config_paths = submanager.models.config.ConfigPaths(
        static=Path(config_path_static),
        dynamic=Path(config_path_dynamic),
        )
    func(config_paths=config_paths, **kwargs)


def handle_parsed_args(parsed_args: argparse.Namespace) -> None:
    """Dispatch to the specified command based on the passed args."""
    # Print version and exit if --version passed
    version: bool = getattr(parsed_args, "version", None)
    if version:
        print_version_string()
        return

    # Execute desired subcommand function if passed, otherwise print help
    try:
        parsed_args.func
    except AttributeError as error:  # If function is not specified
        create_arg_parser().print_usage(file=sys.stderr)
        raise SystemExit(
            submanager.enums.ExitCode.ERROR_PARAMETERS.value) from error
    else:
        run_toplevel_function(**vars(parsed_args))


def cli(sys_argv: Sequence[str] | None = None) -> None:
    """Perform the CLI parsing and execute dispatch."""
    parser_main = create_arg_parser()
    parsed_args = parser_main.parse_args(sys_argv)
    debug: bool = vars(parsed_args).pop("debug")
    try:
        handle_parsed_args(parsed_args)
    except submanager.exceptions.SubManagerUserError as error:
        if debug:
            raise
        formatted_error = submanager.utils.output.format_error(error)
        print(f"\n{'v' * 70}\n{formatted_error}\n{'^' * 70}\n",
              file=sys.stderr)
        raise SystemExit(submanager.enums.ExitCode.ERROR_USER.value) from error


def main(sys_argv: Sequence[str] | None = None) -> None:
    """Run the package though the CLI."""
    cli(sys_argv)


if __name__ == "__main__":
    main()
