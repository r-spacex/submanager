"""Types and type aliases used by the package."""

# Future imports
from __future__ import annotations

# Standard library imports
import os
from typing import (
    Any,
    List,  # Not needed in Python 3.9
    Mapping,  # Import from collections.abc in Python 3.9
    MutableMapping,  # Import from collections.abc in Python 3.9
    NewType,
    Tuple,  # Not needed in Python 3.9
    Type,  # Not needed in Python 3.9
    TYPE_CHECKING,
    Union,  # Not needed in Python 3.10
    )

# Third party imports
import praw.reddit


if TYPE_CHECKING:
    PathLikeStr = Union["os.PathLike[str]", str]
else:
    PathLikeStr = Union[os.PathLike, str]

StrMap = MutableMapping[str, Any]
ExceptTuple = Tuple[Type[Exception], ...]

ConfigDict = Mapping[str, Any]
ConfigDictDynamic = MutableMapping[str, MutableMapping[str, Any]]

AccountConfig = NewType("AccountConfig", Mapping[str, str])
AccountsConfig = NewType("AccountsConfig", Mapping[str, AccountConfig])
AccountsMap = NewType("AccountsMap", Mapping[str, praw.reddit.Reddit])

ChildrenData = List[MutableMapping[str, str]]
SectionData = MutableMapping[str, Union[str, ChildrenData]]
MenuData = NewType("MenuData", List[SectionData])
