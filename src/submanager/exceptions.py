"""Errors and warnings for the package."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import abc
import configparser
from pathlib import (
    Path,
)
from typing import (
    ClassVar,
)

# Third party imports
import praw.exceptions
import prawcore.exceptions
import requests.exceptions
from typing_extensions import (
    Final,
)

# Local imports
import submanager.models.base
import submanager.utils.output
from submanager.types import (
    ExceptTuple,
    PathLikeStr,
)

# ---- Constants ----

DEFAULT_ERROR_MESSAGE: Final[str] = "Error"


# ---- Exception groups ----

PRAW_NOTFOUND_ERRORS: Final[ExceptTuple] = (
    prawcore.exceptions.NotFound,
    prawcore.exceptions.Redirect,
)

PRAW_FORBIDDEN_ERRORS: Final[ExceptTuple] = (
    prawcore.exceptions.Forbidden,
    prawcore.exceptions.UnavailableForLegalReasons,
)

PRAW_RETRIVAL_ERRORS: Final[ExceptTuple] = (
    *PRAW_NOTFOUND_ERRORS,
    *PRAW_FORBIDDEN_ERRORS,
)

PRAW_AUTHORIZATION_ERRORS: Final[ExceptTuple] = (
    praw.exceptions.InvalidImplicitAuth,
    praw.exceptions.ReadOnlyException,
    prawcore.exceptions.Forbidden,
    prawcore.exceptions.InsufficientScope,
    prawcore.exceptions.InvalidToken,
    prawcore.exceptions.OAuthException,
)

PRAW_REDDIT_ERRORS: Final[ExceptTuple] = (
    praw.exceptions.RedditAPIException,
    prawcore.exceptions.ResponseException,
)

PRAW_ALL_ERRORS: Final[ExceptTuple] = (
    praw.exceptions.PRAWException,
    prawcore.exceptions.PrawcoreException,
    configparser.Error,
)

REQUESTS_CONNECTIVITY_ERROS: Final[ExceptTuple] = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)


# ---- Base exception classes


class SubManagerError(Exception):
    """Base class for errors raised by Sub Manager."""

    def __init__(
        self,
        message: str,
        *,
        message_pre: str | None = None,
        message_post: str | BaseException | None = None,
    ) -> None:
        message = message.strip(" ")
        if message_pre is not None:
            message = f"{message_pre.strip(' ')} {message}"
        if message_post is not None:
            if isinstance(message_post, BaseException):
                message_post = submanager.utils.output.format_error(
                    message_post,
                )
            message = f"{message}\n\n{message_post.strip(' ')}"
        super().__init__(message)


class SubManagerUserError(SubManagerError):
    """Errors at runtime that should be correctable via user action."""


class ErrorFillable(SubManagerError, metaclass=abc.ABCMeta):
    """Error with a fillable message."""

    _message_pre: ClassVar[str | None] = DEFAULT_ERROR_MESSAGE
    _message_template: ClassVar[str] = "occurred"
    _message_post: ClassVar[str | None] = None

    def __init__(
        self,
        *,
        message_pre: str | None = None,
        message_post: str | BaseException | None = None,
        **extra_fillables: str,
    ) -> None:
        if message_pre is None:
            message_pre = self._message_pre
        if message_post is None:
            message_post = self._message_post
        message = self._message_template.format(**extra_fillables)
        super().__init__(
            message=message,
            message_pre=message_pre,
            message_post=message_post,
        )


class ErrorWithConfigItem(ErrorFillable):
    """Something's wrong with an endpoint."""

    _message_pre: ClassVar[str] = DEFAULT_ERROR_MESSAGE
    _message_template: ClassVar[str] = "in item {config}"

    def __init__(
        self,
        config_item: submanager.models.base.ItemConfig,
        *,
        message_pre: str | None = None,
        message_post: str | BaseException | None = None,
        **extra_fillables: str,
    ) -> None:
        self.config_item = config_item
        super().__init__(
            message_pre=message_pre,
            message_post=message_post,
            config=f"{config_item.uid} - {config_item.description!r}",
            **extra_fillables,
        )


class SubManagerValueError(SubManagerError, ValueError):
    """General programmer errors related to values not being as expected."""


# ---- Reddit-related exceptions ----


class RedditError(SubManagerError):
    """Something went wrong with the data returned from the Reddit API."""


class RedditConnectionError(RedditError, SubManagerUserError):
    """Could not connect to Reddit."""


class RedditNetworkError(RedditConnectionError):
    """Cannot connect to Reddit at all due to lack of a network connection."""


class RedditHTTPError(RedditConnectionError):
    """Got a HTTP error when testing connectivity to Reddit."""


class RedditObjectNotFoundError(
    ErrorWithConfigItem,
    RedditError,
    SubManagerUserError,
):
    """Could not find the object on Reddit."""


class SubredditNotFoundError(RedditObjectNotFoundError):
    """Could not access subreddit due to name being not found or blocked."""


class RedditModelError(ErrorWithConfigItem, RedditError):
    """The object's data model didn't match that required."""


class PostTypeError(ErrorWithConfigItem, RedditError, SubManagerUserError):
    """The post was found, but it was of the wrong type (link/self)."""


class WidgetTypeError(ErrorWithConfigItem, RedditError, SubManagerUserError):
    """A widget was found with the given name, but is of unsupported type."""


# ---- Permissions exceptions ----


class RedditPermissionError(RedditError, SubManagerUserError):
    """Errors related to not having Reddit permissions to perform an action."""


class RedditObjectNotAccessibleError(
    ErrorWithConfigItem,
    RedditPermissionError,
):
    """Found the object but could not access it with the current account."""


class SubredditNotAccessibleError(RedditObjectNotAccessibleError):
    """Found the subreddit but it was private, quarentined or banned."""


class NotAModError(ErrorWithConfigItem, RedditPermissionError):
    """The user needs to be a moderator to perform the requested action."""


class NotOPError(ErrorWithConfigItem, RedditPermissionError):
    """The user needs to be the post OP to perform the requested action."""


class WikiPagePermissionError(ErrorWithConfigItem, RedditPermissionError):
    """The user is not authorized to edit the given wiki page."""


# ---- Account and authorization-related exceptions ----


class TestPageNotFoundWarning(DeprecationWarning):
    """A sub/page checked for account authorization was not found."""


class NoCommonScopesWarning(DeprecationWarning):
    """The account didn't have any scopes that could be tested for access."""


class ErrorWithAccount(ErrorFillable):
    """Something's wrong with the Reddit account configuration."""

    _message_pre: ClassVar[str] = DEFAULT_ERROR_MESSAGE
    _message_template: ClassVar[str] = "with account {account_key!r}"

    def __init__(
        self,
        account_key: str,
        *,
        message_pre: str | None = None,
        message_post: str | BaseException | None = None,
        **extra_fillables: str,
    ) -> None:
        self.account_key = account_key
        super().__init__(
            message_pre=message_pre,
            message_post=message_post,
            account_key=account_key,
            **extra_fillables,
        )


class ScopeCheckError(ErrorWithAccount, RedditError, SubManagerUserError):
    """Error attempting to get authorized scopes for the account token."""


class AccountCheckError(ErrorWithAccount, RedditError, SubManagerUserError):
    """Cannot perform an operation checking that the account is authorized."""


class AuthError(RedditError, SubManagerUserError):
    """Errors related to user authentication."""


class AccountCheckAuthError(AccountCheckError, AuthError):
    """Authorization error occurred when checking the user account."""


class RedditReadOnlyError(ErrorWithAccount, AuthError):
    """The Reddit instance was not authorized properly ."""


class NoAuthorizedScopesError(ErrorWithAccount, AuthError):
    """The user has no authorized scopes."""


class InsufficientScopeError(ErrorWithConfigItem, AuthError):
    """The token needs a particular OAUTH scope it wasn't authorized for."""


# ---- Config-related exceptions ----


class ConfigError(SubManagerUserError):
    """There is a problem with the Sub Manager configuration."""


class ConfigErrorWithPath(ErrorFillable, ConfigError):
    """Config errors that involve a config file at a specific path."""

    _message_pre: ClassVar[str] = DEFAULT_ERROR_MESSAGE
    _message_template: ClassVar[
        str
    ] = "for config file at path {config_path!r}"

    def __init__(
        self,
        config_path: PathLikeStr,
        *,
        message_pre: str | None = None,
        message_post: str | BaseException | None = None,
        **extra_fillables: str,
    ) -> None:
        self.config_path = Path(config_path)
        super().__init__(
            message_pre=message_pre,
            message_post=message_post,
            config_path=self.config_path.as_posix(),
            **extra_fillables,
        )


class ConfigNotFoundError(ConfigErrorWithPath):
    """The Sub Manager configuration file is not found."""

    _message_pre: ClassVar[str] = "File not found"


class ConfigExistsError(ConfigErrorWithPath):
    """The Sub Manager configuration file already exists when generated."""

    _message_pre: ClassVar[str] = "File already exists"


class ConfigExtensionError(ConfigErrorWithPath):
    """The Sub Manager config file is not in a recognized format."""

    _message_pre: ClassVar[str] = "File extension not recognized"


class ConfigParsingError(ConfigErrorWithPath):
    """The Sub Manager config file format is not valid."""

    _message_pre: ClassVar[str] = "File parsing error"


class ConfigEmptyError(ConfigErrorWithPath):
    """The Sub Manager config file format is empty."""

    _message_pre: ClassVar[str] = "File empty"


class ConfigDataTypeError(ConfigErrorWithPath):
    """The Sub Manager config file must be a dict/mapping."""

    _message_pre: ClassVar[str] = "Data structure not a dict/table/mapping"


class ConfigValidationError(ConfigErrorWithPath):
    """The Sub Manager config file has invalid property value(s)."""

    _message_pre: ClassVar[str] = "Validation failed"


class ConfigDefaultError(ConfigErrorWithPath):
    """The Sub Manager configuration file has not been configured."""

    _message_pre: ClassVar[str] = "Unconfigured defaults"
    _message_post: ClassVar[str] = "Make sure to replace all EXAMPLE values."


class AccountConfigError(ErrorWithAccount, ConfigError):
    """PRAW error loading the Reddit account configuration."""

    _message_pre: ClassVar[str] = "PRAW error on initialization"


# ---- Misc errors ----


class LockTimeoutError(SubManagerError):
    """The timeout was exceeded while attempting to acquire a file lock."""


class PlatformUnsupportedError(SubManagerUserError):
    """The operation is unsupported for the current platform."""
