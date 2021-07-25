"""Low level utilities to load, serialize, and save config files."""

# Future imports
from __future__ import annotations

# Standard library imports
import json
from pathlib import Path

# Third party imports
import pydantic
import toml
from typing_extensions import (
    Final,  # Added to typing in Python 3.8
    )

# Local imports
import submanager.exceptions
from submanager.constants import (
    CONFIG_PATH_DYNAMIC,
    )
from submanager.types import (
    ConfigDict,
    PathLikeStr,
    )

SUPPORTED_CONFIG_FORMATS: Final[frozenset[str]] = frozenset({"json", "toml"})


def serialize_config(
        config: ConfigDict | pydantic.BaseModel,
        output_format: str = "json",
        ) -> str:
    """Convert the configuration data to a serializable text form."""
    if output_format == "json":
        if isinstance(config, pydantic.BaseModel):
            serialized_config = config.json(indent=4)
        else:
            serialized_config = json.dumps(dict(config), indent=4)
    elif output_format == "toml":
        serialized_config = toml.dumps(dict(config))
    else:
        raise submanager.exceptions.ConfigError(
            f"Output format {output_format!r} must be in "
            f"{SUPPORTED_CONFIG_FORMATS}")
    return serialized_config


def write_config(
        config: ConfigDict | pydantic.BaseModel,
        config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
        ) -> str:
    """Write the passed config to the specified config path."""
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        serialized_config = serialize_config(
            config=config, output_format=config_path.suffix[1:])
    except submanager.exceptions.ConfigError as error:
        raise submanager.exceptions.ConfigTypeError(
            config_path, message_post=error) from error
    with open(config_path, mode="w",
              encoding="utf-8", newline="\n") as config_file:
        config_file.write(serialized_config)
    return serialized_config


def load_config(config_path: PathLikeStr) -> ConfigDict:
    """Load the config file at the specified path."""
    config_path = Path(config_path)
    with open(config_path, mode="r", encoding="utf-8") as config_file:
        config: ConfigDict
        if config_path.suffix == ".json":
            config = dict(json.load(config_file))
        elif config_path.suffix == ".toml":
            config = dict(toml.load(config_file))
        else:
            raise submanager.exceptions.ConfigTypeError(
                config_path,
                message_post=submanager.exceptions.ConfigError(
                    f"Input format {config_path.suffix!r} must be in "
                    f"{SUPPORTED_CONFIG_FORMATS}"),
                )
    return config