"""Base classes for sync endpoints."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import abc

# Third party imports
import praw.models.reddit.subreddit
import praw.reddit
import prawcore.exceptions
from typing_extensions import (
    Protocol,
    runtime_checkable,
)

# Local imports
import submanager.exceptions
import submanager.models.config
from submanager.types import (
    MenuData,
)

# ---- Protocols ----


@runtime_checkable
class EditableTextWidgetModeration(Protocol):
    """Widget moderation object with editable text."""

    @abc.abstractmethod
    def update(self, text: str) -> None:
        """Update method that takes a string."""
        raise NotImplementedError


@runtime_checkable
class EditableTextWidget(Protocol):
    """An object with text that can be edited."""

    mod: EditableTextWidgetModeration
    text: str


@runtime_checkable
class RevisionDateCheckable(Protocol):
    """An object with a retrievable revision date."""

    @property
    @abc.abstractmethod
    def revision_date(self) -> int:
        """Get the date the sync endpoint was last updated."""
        raise NotImplementedError


# ---- Base classes ----


class SyncEndpoint(metaclass=abc.ABCMeta):
    """Abstraction of a source or target for a Reddit sync action."""

    @abc.abstractmethod
    def _setup_object(self) -> object:
        """Set up the underlying PRAW object the endpoint will use."""
        raise NotImplementedError

    def _validate_object(self) -> None:
        """Validate the the object exits and has the needed properties."""
        try:
            self.content
        except submanager.exceptions.PRAW_NOTFOUND_ERRORS as error:
            raise submanager.exceptions.RedditObjectNotFoundError(
                self.config,
                message_pre=f"Reddit object {self._object!r} not found",
                message_post=error,
            ) from error
        except submanager.exceptions.PRAW_FORBIDDEN_ERRORS as error:
            raise submanager.exceptions.RedditObjectNotAccessibleError(
                self.config,
                message_pre=(
                    f"Reddit object {self._object!r} found but not accessible "
                    f"from account {self.config.context.account!r}"
                ),
                message_post=error,
            ) from error

    def __init__(
        self,
        config: submanager.models.config.EndpointConfig,
        reddit: praw.reddit.Reddit,
        *,
        validate: bool = False,
        raise_error: bool = True,
    ) -> None:
        self.config = config
        self._reddit = reddit
        self._validated: bool | None = None

        self._subreddit: praw.models.reddit.subreddit.Subreddit = (
            self._reddit.subreddit(self.config.context.subreddit)
        )
        try:
            self._subreddit.id
        except submanager.exceptions.PRAW_NOTFOUND_ERRORS as error:
            raise submanager.exceptions.SubredditNotFoundError(
                self.config,
                message_pre=(
                    f"Sub 'r/{self.config.context.subreddit}' not found"
                ),
                message_post=error,
            ) from error
        except submanager.exceptions.PRAW_FORBIDDEN_ERRORS as error:
            raise submanager.exceptions.SubredditNotAccessibleError(
                self.config,
                message_pre=(
                    f"Sub 'r/{self.config.context.subreddit}' found but not "
                    "accessible from current account "
                    f"{self.config.context.account!r}"
                ),
                message_post=error,
            ) from error

        self._object = self._setup_object()
        if validate:
            self._validated = self.validate(raise_error=raise_error)

    @property
    @abc.abstractmethod
    def content(self) -> str | MenuData:
        """Get the current content of the sync endpoint."""
        raise NotImplementedError

    @abc.abstractmethod
    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the sync endpoint with the given content."""
        raise NotImplementedError

    @abc.abstractmethod
    def _check_is_editable(self, raise_error: bool = True) -> bool:
        """Check if the object can be edited by the user, w/o validation."""

    def check_is_editable(self, raise_error: bool = True) -> bool | None:
        """Check if the object can be edited by the user, with validation."""
        if self._validated is None or (
            self._validated is False and raise_error
        ):
            self.validate(raise_error=raise_error)
        if not self.is_valid:
            return None
        return self._check_is_editable(raise_error=raise_error)

    @property
    def is_editable(self) -> bool | None:
        """Is True if the object is editable by the user, False otherwise."""
        return self.check_is_editable(raise_error=False)

    @property
    def is_valid(self) -> bool:
        """Is true if the object is validated, false if not."""
        if self._validated is None:
            return self.validate(raise_error=False)
        return self._validated

    def validate(self, raise_error: bool = True) -> bool:
        """Validate that the sync endpoint points to a valid Reddit object."""
        try:
            self._validate_object()
        except submanager.exceptions.RedditError:
            self._validated = False
            if not raise_error:
                return False
            raise

        self._validated = True
        return True


class WidgetSyncEndpoint(SyncEndpoint, metaclass=abc.ABCMeta):
    """Sync endpoint reprisenting a generic New Reddit widget."""

    _object: praw.models.reddit.widgets.Widget | EditableTextWidget

    @abc.abstractmethod
    def _setup_object(
        self,
    ) -> praw.models.reddit.widgets.Widget | EditableTextWidget:
        """Set up the underlying PRAW object the endpoint will use."""
        raise NotImplementedError

    def _check_is_editable(self, raise_error: bool = True) -> bool:
        """Is True if the widget is editable, False otherwise."""
        try:
            # static analysis: ignore[incompatible_call]
            self._object.mod.update()  # type: ignore[call-arg]
        except prawcore.exceptions.Forbidden as error:
            if not raise_error:
                return False
            raise submanager.exceptions.NotAModError(
                self.config,
                message_pre=(
                    f"Account {self.config.context.account!r} must "
                    "be a moderator to update widgets"
                ),
                message_post=error,
            ) from error

        return True
