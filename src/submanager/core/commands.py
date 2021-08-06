"""Handle the high-level commands other than the core run code."""

# Future imports
from __future__ import annotations

# Standard library imports
from pathlib import Path

# Local imports
import submanager.config.static
import submanager.core.initialization
import submanager.exceptions
import submanager.models.config
import submanager.utils.output
import submanager.validation.endpoints
import submanager.validation.validate


def run_get_config_info(
        config_paths: submanager.models.config.ConfigPaths | None = None,
        *,
        endpoints: bool = False,
        ) -> None:
    """Print basic information about the current configuration."""
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()

    # Print config file path information
    path_items: list[tuple[str, Path]] = [
        ("static", config_paths.static), ("dynamic", config_paths.dynamic)]
    pad_chars = max([len(path_item[0]) for path_item in path_items])
    print()
    for config_name, config_path in path_items:
        config_exists = config_path.exists()
        config_status = "    [FOUND]" if config_exists else "[NOT FOUND]"
        print(
            f"{config_name.title(): >{pad_chars}} config path:",
            config_status,
            f'"{config_path.as_posix()}"')
    print()

    # Print endpoint list information
    if endpoints:
        static_config, __ = submanager.core.initialization.setup_config(
            config_paths=config_paths)
        enabled_endpoints = submanager.validation.endpoints.get_all_endpoints(
            static_config=static_config, include_disabled=False)
        all_endpoints = submanager.validation.endpoints.get_all_endpoints(
            static_config=static_config, include_disabled=True)
        print(" ###### Source/target sync endpoints ######")
        for endpoint in all_endpoints:
            enabled = endpoint in enabled_endpoints
            endpoint_status = " [ENABLED]" if enabled else "[DISABLED]"
            print(f"{endpoint_status}  {endpoint.uid}")
        print()


def run_generate_config(
        config_paths: submanager.models.config.ConfigPaths | None = None,
        *,
        force: bool = False,
        exist_ok: bool = False,
        ) -> None:
    """Generate the various config files for sub manager."""
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()
    config_exists = submanager.config.static.generate_static_config(
        config_path=config_paths.static, force=force, exist_ok=exist_ok)

    # Generate the appropriate message depending on what happened
    if not config_exists:
        action = "generated"
    elif force:
        action = "overwritten"
    else:
        action = "already exists"
    message = f"Config {action} at {config_paths.static.as_posix()!r}"
    print(message)


def run_validate_config(
        config_paths: submanager.models.config.ConfigPaths | None = None,
        *,
        include_disabled: bool = False,
        offline_only: bool = False,
        minimal: bool = False,
        ) -> None:
    """Check if the config is valid, raising an error if it is not."""
    wprint = submanager.utils.output.FancyPrinter()
    wprint("Validating configuration in "
           f"{'offline' if offline_only else 'online'} mode", level=2)
    try:
        submanager.validation.validate.validate_config(
            config_paths=config_paths,
            offline_only=offline_only,
            minimal=minimal,
            include_disabled=include_disabled,
            raise_error=True,
            verbose=True,
            )
    except submanager.exceptions.SubManagerUserError:
        wprint("Config validation FAILED", level=2)
        raise
    except Exception:
        wprint("Unexpected error occured during config validation:", level=2)
        raise
    else:
        wprint("Config validation SUCCEEDED", level=2)
