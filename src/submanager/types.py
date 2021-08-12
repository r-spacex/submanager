"""Types and type aliases used by the package."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import datetime
import os
from typing import (
    TYPE_CHECKING,
    Any,
    List,
    Mapping,
    MutableMapping,
    NewType,
    Tuple,
    Type,
    Union,
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

AccountsMap = NewType("AccountsMap", Mapping[str, praw.reddit.Reddit])

ChildrenData = List[MutableMapping[str, str]]
SectionData = MutableMapping[str, Union[str, ChildrenData]]
MenuData = NewType("MenuData", List[SectionData])

TemplateVars = MutableMapping[str, Union[str, int, float, datetime.datetime]]
