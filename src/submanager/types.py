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
    Tuple,  # Not needed in Python 3.9
    Type,  # Not needed in Python 3.9
    TYPE_CHECKING,
    Union,  # Not needed in Python 3.9
    )

# Third party imports
import praw.reddit
import praw.util.token_manager


if TYPE_CHECKING:
    PathLikeStr = Union["os.PathLike[str]", str]
else:
    PathLikeStr = Union[os.PathLike, str]

StrMap = MutableMapping[str, Any]
ExceptTuple = Tuple[Type[Exception], ...]

AccountConfig = MutableMapping[str, str]
AccountsConfig = Mapping[str, AccountConfig]
AccountConfigProcessed = MutableMapping[str, Union[
    str, praw.util.token_manager.FileTokenManager]]
AccountsConfigProcessed = Mapping[str, AccountConfigProcessed]
AccountsMap = Mapping[str, praw.reddit.Reddit]
ConfigDict = Mapping[str, Any]
ConfigDictDynamic = MutableMapping[str, MutableMapping[str, Any]]

ChildrenData = List[MutableMapping[str, str]]
SectionData = MutableMapping[str, Union[str, ChildrenData]]
MenuData = List[SectionData]
