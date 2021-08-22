"""Handle the high-level commands other than the core run code."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import importlib.resources  # nosemgrep
import sys
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
import submanager.config.static
import submanager.core.initialization
import submanager.exceptions
import submanager.models.config
import submanager.utils.output
import submanager.validation.endpoints
import submanager.validation.validate
from submanager.constants import (
    SECURE_DIR_MODE,
    SECURE_FILE_MODE,
)
from submanager.types import (
    PathLikeStr,
)

# ---- Constants ----

USER_CONFIG_PATH: Final[Path] = platformdirs.user_config_path()
SYSTEMD_USER_DIR: Final[Path] = USER_CONFIG_PATH / "systemd" / "user"
SERVICE_FILENAME_INPUT: Final[str] = "submanager.service"
SERVICE_FILENAME_OUTPUT: Final[str] = "submanager{suffix}.service"


def run_get_config_info(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    endpoints: bool = False,
    verbose: bool = True,
) -> None:
    """Print basic information about the current configuration."""
    vprint = submanager.utils.output.VerbosePrinter(enable=verbose)
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()

    # Print config file path information
    path_items: list[tuple[str, Path]] = [
        ("static", config_paths.static),
        ("dynamic", config_paths.dynamic),
    ]
    pad_chars = max(len(path_item[0]) for path_item in path_items)
    vprint()
    for config_name, config_path in path_items:
        config_exists = config_path.exists()
        config_status = "    [FOUND]" if config_exists else "[NOT FOUND]"
        vprint(
            f"{config_name.title(): >{pad_chars}} config path:",
            config_status,
            f'"{config_path.as_posix()}"',
        )
    vprint()

    # Print endpoint list information
    if endpoints:
        static_config, __ = submanager.core.initialization.setup_config(
            config_paths=config_paths,
        )
        enabled_endpoints = submanager.validation.endpoints.get_all_endpoints(
            static_config=static_config,
            include_disabled=False,
        )
        all_endpoints = submanager.validation.endpoints.get_all_endpoints(
            static_config=static_config,
            include_disabled=True,
        )
        vprint(" ###### Source/target sync endpoints ######")
        for endpoint in all_endpoints:
            enabled = endpoint in enabled_endpoints
            endpoint_status = " [ENABLED]" if enabled else "[DISABLED]"
            vprint(f"{endpoint_status}  {endpoint.uid}")
        vprint()


def run_install_service(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    suffix: str | None = None,
    *,
    output_dir: PathLikeStr = SYSTEMD_USER_DIR,
    force_unsupported: bool = False,
    verbose: bool = True,
) -> None:
    """Install a Systemd user service on a Linux machine."""
    if not (force_unsupported or sys.platform.startswith("linux")):
        raise submanager.exceptions.PlatformUnsupportedError(
            "Service install not currently supported on non-Linux platforms",
        )

    # Set up variables and paths
    vprint = submanager.utils.output.VerbosePrinter(enable=verbose)
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()
    output_dir = Path(output_dir)
    if suffix:
        suffix = f"-{suffix}"
    else:
        suffix = ""
    output_dir.mkdir(mode=SECURE_DIR_MODE, parents=True, exist_ok=True)
    output_path = output_dir / SERVICE_FILENAME_OUTPUT.format(suffix=suffix)

    # Load service file content
    with importlib.resources.open_text(
        submanager,
        SERVICE_FILENAME_INPUT,
        encoding="utf-8",
    ) as service_file_input:
        service_content = service_file_input.read()

    # Replace variables in content
    service_content = service_content.format(
        interpreter_path=Path(sys.executable).as_posix(),
        config_path_static=config_paths.static.as_posix(),
        config_path_dynamic=config_paths.dynamic.as_posix(),
    )

    # Write service file content
    with open(
        output_path,
        mode="w",
        encoding="utf-8",
        newline="\n",
    ) as service_file_output:
        service_file_output.write(service_content)
    output_path.chmod(SECURE_FILE_MODE)

    # Print information
    vprint(f"Generated service unit at path {output_path.as_posix()!r}\n")
    vprint(f"Use `systemctl --user <command> {output_path.stem}` to interact")
    vprint("For example, `enable`, `disable`, `start`, `stop` and `status`")
    vprint(f"Use `journalctl --user -xe -u {output_path.stem}` for the log\n")


def run_generate_config(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    force: bool = False,
    exist_ok: bool = False,
    verbose: bool = True,
) -> None:
    """Generate the various config files for sub manager."""
    vprint = submanager.utils.output.VerbosePrinter(enable=verbose)
    if config_paths is None:
        config_paths = submanager.models.config.ConfigPaths()
    config_exists = submanager.config.static.generate_static_config(
        config_path=config_paths.static,
        force=force,
        exist_ok=exist_ok,
    )

    # Generate the appropriate message depending on what happened
    if not config_exists:
        action = "generated"
    elif force:
        action = "overwritten"
    else:
        action = "already exists"
    message = f"Config {action} at {config_paths.static.as_posix()!r}"
    vprint(message)


def run_validate_config(
    config_paths: submanager.models.config.ConfigPaths | None = None,
    *,
    include_disabled: bool = False,
    offline_only: bool = False,
    minimal: bool = False,
    verbose: bool = True,
) -> None:
    """Check if the config is valid, raising an error if it is not."""
    wprint = submanager.utils.output.FancyPrinter(enable=verbose)
    wprint(
        "Validating configuration in "
        f"{'offline' if offline_only else 'online'} mode",
        level=2,
    )
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
        wprint("Unexpected error occurred during config validation:", level=2)
        raise
    else:
        wprint("Config validation SUCCEEDED", level=2)
