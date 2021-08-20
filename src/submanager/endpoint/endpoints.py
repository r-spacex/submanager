"""Builtin classes for sync endpoints."""

# Future imports
from __future__ import (
    annotations,
)

# Third party imports
import praw.models.reddit.submission
import praw.models.reddit.widgets
import prawcore.exceptions
from typing_extensions import (
    Literal,
)

# Local imports
import submanager.endpoint.base
import submanager.exceptions
from submanager.types import (
    MenuData,
)


class ThreadSyncEndpoint(
    submanager.endpoint.base.SyncEndpoint,
    submanager.endpoint.base.RevisionDateCheckable,
):
    """Sync endpoint reprisenting a Reddit thread (selfpost submission)."""

    _object: praw.models.reddit.submission.Submission

    def _setup_object(self) -> praw.models.reddit.submission.Submission:
        """Set up the submission object for syncing to a thread."""
        submission: praw.models.reddit.submission.Submission = (
            self._reddit.submission(id=self.config.endpoint_name)
        )
        return submission

    @property
    def content(self) -> str:
        """Get the current submission's selftext."""
        submission_text: str = self._object.selftext
        return submission_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the thread's text to be that passed."""
        self._object.edit(str(new_content))

    def _check_is_editable(self, raise_error: bool = True) -> bool:
        """Is True if the thread is editable, False otherwise."""
        try:
            self.edit(self.content)
        except prawcore.exceptions.Forbidden as error:
            if not raise_error:
                return False
            account = self.config.context.account
            post_title = self._object.title
            post_id = self._object.id
            author_name = self._object.author.name
            raise submanager.exceptions.NotOPError(
                self.config,
                message_pre=(
                    f"Account {account!r} used to edit "
                    f"the post {post_title!r} ({post_id}) "
                    f"must be the OP {author_name!r}"
                ),
                message_post=error,
            ) from error
        except praw.exceptions.RedditAPIException as error:
            for reddit_error in error.items:
                error_type = reddit_error.error_type
                if error_type.lower().strip() == "placeholder":
                    break
            else:
                raise

            if not raise_error:
                return False
            raise submanager.exceptions.PostTypeError(
                self.config,
                message_pre=(
                    f"Cannot edit link post {self._object.title!r} "
                    f"({self._object.id}); must be a selfpost"
                ),
                message_post=error,
            ) from error

        return True

    @property
    def revision_date(self) -> int:
        """Get the date the thread was last edited."""
        edited_date: int | Literal[False] = self._object.edited
        if not edited_date:
            edited_date = self._object.created_utc
        return edited_date


class WikiSyncEndpoint(
    submanager.endpoint.base.SyncEndpoint,
    submanager.endpoint.base.RevisionDateCheckable,
):
    """Sync endpoint reprisenting a Reddit wiki page."""

    _object: praw.models.reddit.wikipage.WikiPage

    def _setup_object(self) -> praw.models.reddit.wikipage.WikiPage:
        """Set up the wiki page object for syncing to a wiki page."""
        wiki_page: praw.models.reddit.wikipage.WikiPage = self._subreddit.wiki[
            self.config.endpoint_name
        ]
        return wiki_page

    @property
    def content(self) -> str:
        """Get the current text content of the wiki page."""
        wiki_text: str = self._object.content_md
        return wiki_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the wiki page with the given text."""
        self._object.edit(str(new_content), reason=reason)

    def _check_is_editable(self, raise_error: bool = True) -> bool:
        """Is True if the wiki page is editable, False otherwise."""
        try:
            self.edit(self.content, reason="Validation edit from Sub Manager")
        except (
            prawcore.exceptions.Forbidden,
            praw.exceptions.RedditAPIException,
        ) as error:
            if isinstance(error, praw.exceptions.RedditAPIException):
                expected_error = any(
                    reddit_error.error_type.upper() == "WIKI_CREATE_ERROR"
                    for reddit_error in error.items
                )
                if not expected_error:
                    raise

            if not raise_error:
                return False
            raise submanager.exceptions.WikiPagePermissionError(
                self.config,
                message_pre=(
                    f"Account {self.config.context.account!r} "
                    "must be authorized to edit wiki page "
                    f"{self.config.endpoint_name!r}"
                ),
                message_post=error,
            ) from error

        return True

    @property
    def revision_date(self) -> int:
        """Get the date the wiki page was last updated."""
        revision_timestamp: int = self._object.revision_date
        return revision_timestamp


class MenuSyncEndpoint(submanager.endpoint.base.WidgetSyncEndpoint):
    """Sync endpoint reprisenting a New Reddit top bar menu widget."""

    _object: praw.models.reddit.widgets.Menu

    def _setup_object(self) -> praw.models.reddit.widgets.Menu:
        """Set up the menu widget object for syncing to a menu."""
        widgets = self._subreddit.widgets.topbar
        for widget in widgets:
            if isinstance(widget, praw.models.reddit.widgets.Menu):
                return widget
        raise submanager.exceptions.RedditObjectNotFoundError(
            self.config,
            message_pre=(
                f"Menu widget not found in 'r/{self.config.context.subreddit}'"
            ),
            message_post=(
                "You may need to create it by adding at least one menu item."
            ),
        )

    @property
    def content(self) -> MenuData:
        """Get the current structured data in the menu widget."""
        attribute_name = "data"
        menu_data: MenuData | None = getattr(
            self._object,
            attribute_name,
            None,
        )
        if menu_data is None:
            raise submanager.exceptions.RedditModelError(
                self.config,
                message_pre=(
                    f"Menu widget {self._object!r} "
                    f"missing attribute {attribute_name!r}"
                ),
            )
        return menu_data

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the menu with the given structured data."""
        self._object.mod.update(data=new_content)


class SidebarSyncEndpoint(submanager.endpoint.base.WidgetSyncEndpoint):
    """Sync endpoint reprisenting a New Reddit sidebar text content widget."""

    _object: submanager.endpoint.base.EditableTextWidget

    def _setup_object(self) -> submanager.endpoint.base.EditableTextWidget:
        """Set up the widget object for syncing to a sidebar widget."""
        widgets = self._subreddit.widgets.sidebar
        names: list[str] = []
        for widget in widgets:
            widget_name: str | None = getattr(widget, "shortName", None)
            if not widget_name:
                continue
            if widget_name == self.config.endpoint_name:
                if isinstance(
                    widget,
                    submanager.endpoint.base.EditableTextWidget,
                ):
                    return widget
                raise submanager.exceptions.WidgetTypeError(
                    self.config,
                    message_pre=(
                        f"Widget {self.config.endpoint_name!r} "
                        f"has unsupported type {type(widget)!r}"
                    ),
                    message_post=(
                        "Only text-content widgets are currently supported."
                    ),
                )
            names.append(widget_name)
        endpoint_name = self.config.endpoint_name
        subreddit_name = self.config.context.subreddit
        widget_names = names if names else "None"
        raise submanager.exceptions.RedditObjectNotFoundError(
            self.config,
            message_pre=(
                f"Sidebar widget {endpoint_name!r} "
                f"not found in 'r/{subreddit_name}' "
                f"(found widgets: {widget_names})"
            ),
            message_post="If this is not a typo, please create it first.",
        )

    @property
    def content(self) -> str:
        """Get the current text content of the sidebar widget."""
        widget_text: str = self._object.text
        return widget_text

    def edit(self, new_content: object, reason: str = "") -> None:
        """Update the sidebar widget with the given text content."""
        self._object.mod.update(text=str(new_content))
