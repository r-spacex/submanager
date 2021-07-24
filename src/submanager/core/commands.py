"""Handle the high-level commands other than the core run code."""

# Future imports
from __future__ import annotations

# Local imports
import submanager.config.static
import submanager.exceptions
import submanager.models.config
import submanager.utils.output
import submanager.validation.validate


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
    message = f"Config {{action}} at {config_paths.static.as_posix()!r}"
    if not config_exists:
        action = "generated"
    elif force:
        action = "overwritten"
    else:
        action = "already exists"
    print(message.format(action=action))


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
