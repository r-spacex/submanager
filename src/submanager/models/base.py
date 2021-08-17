# static analysis: ignore
"""Base classes for building the models used by the package."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import abc
from typing import (
    Mapping,
)

# Third party imports
import pydantic

# Local imports
import submanager.models.utils
from submanager.models.types import (
    ItemIDStr,
    StripStr,
)


class CustomBaseModel(
    pydantic.BaseModel,
    validate_all=True,
    extra=pydantic.Extra.forbid,
    allow_mutation=False,
    validate_assignment=True,
    metaclass=abc.ABCMeta,
):
    """Locally-customized Pydantic BaseModel."""


class CustomMutableBaseModel(
    CustomBaseModel,
    allow_mutation=True,
    metaclass=abc.ABCMeta,
):
    """Custom BaseModel that allows mutation."""


class ItemConfig(CustomBaseModel, metaclass=abc.ABCMeta):
    """Base class for an atomic unit in the config hierarchy."""

    description: pydantic.StrictStr = ""
    enabled: bool = True
    uid: ItemIDStr


class ContextConfig(CustomBaseModel):
    """Local context configuration for the bot."""

    account: StripStr
    subreddit: StripStr

    @pydantic.validator("account", pre=True)
    def check_account_found(  # pylint: disable = no-self-use, no-self-argument
        cls,
        value: submanager.models.utils.MissingAccount | str,
    ) -> str:
        """Check that the account is present in the global accounts table."""
        if isinstance(value, submanager.models.utils.MissingAccount):
            raise ValueError(
                f"Account key '{value}' not listed in accounts table",
            )
        return value


class ItemWithContextConfig(ItemConfig, metaclass=abc.ABCMeta):
    """Base class reprisenting a config item that has a Reddit context."""

    context: ContextConfig


class DynamicItemConfig(CustomMutableBaseModel, metaclass=abc.ABCMeta):
    """Base class for the dynamic configuration of a generic item."""


class ManagerConfig(CustomBaseModel, metaclass=abc.ABCMeta):
    """Base class for manager modules."""

    enabled: bool = True


class ItemManagerConfig(ManagerConfig, metaclass=abc.ABCMeta):
    """Base class for managers that deal with arbitrary discrete items."""

    items: Mapping[StripStr, ItemConfig] = {}


class DynamicItemManagerConfig(CustomMutableBaseModel, metaclass=abc.ABCMeta):
    """Base class for dynamic config for ItemManagers."""

    items: Mapping[StripStr, DynamicItemConfig] = {}
