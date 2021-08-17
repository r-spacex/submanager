"""Validate each Reddit object registered for a configuration."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import enum
import warnings
from typing import (
    Collection,
)

# Third party imports
import praw.reddit
from typing_extensions import (
    Final,
)

# Local imports
import submanager.exceptions
import submanager.utils.output
from submanager.types import (
    AccountsMap,
)

# ---- Constants and enums ----

TESTABLE_SCOPES: Final[frozenset[str]] = frozenset(
    ("*", "identity", "read", "wikiread"),
)
TEST_PAGE_WIKI: Final[str] = "index"
TEST_SUB_POST: Final[str] = "all"
TEST_SUB_WIKI: Final[str] = "help"
TEST_USERNAME: Final[str] = "spez"


@enum.unique
class ScopeCheck(enum.Enum):
    """The available scope to test a Reddit request for."""

    IDENTITY = "identity"
    READ_POST = "read"
    READ_WIKI = "readwiki"
    USERNAME = "any"


# ---- Reddit request tests ----


def try_perform_test_request(
    reddit: praw.reddit.Reddit,
    account_key: str,
    scope_check: ScopeCheck,
) -> None:
    """Attempt to perform a test Reddit request against a valid scope."""
    warning_message = (
        # static analysis: ignore[missing_f]
        f"Error finding {{test_item}} testing scope {scope_check.value!r} "
        f"with account {account_key!r} ({{error}})"
    )

    # Ideally, simply check the account's identity
    if scope_check is ScopeCheck.IDENTITY:
        reddit.user.me()

    # Read an arbitrary thread
    elif scope_check is ScopeCheck.READ_POST:
        try:
            list(reddit.subreddit(TEST_SUB_POST).hot(limit=1))[0].id
        except submanager.exceptions.PRAW_NOTFOUND_ERRORS as error:
            warning_message = warning_message.format(
                test_item=f"sub 'r/{TEST_SUB_POST}'",
                error=submanager.utils.output.format_error(error),
            )
            warnings.warn(
                warning_message,
                submanager.exceptions.TestPageNotFoundWarning,
                stacklevel=2,
            )

    # Read an arbitrary wiki page
    elif scope_check is ScopeCheck.READ_WIKI:
        try:
            reddit.subreddit(TEST_SUB_WIKI).wiki[TEST_PAGE_WIKI].content_md
        except (  # noqa: WPS440
            submanager.exceptions.PRAW_NOTFOUND_ERRORS
        ) as error:
            warning_message = warning_message.format(
                test_item=(
                    f"sub 'r/{TEST_SUB_WIKI}', wiki page {TEST_PAGE_WIKI!r}"
                ),
                error=submanager.utils.output.format_error(error),
            )
            warnings.warn(
                warning_message,
                submanager.exceptions.TestPageNotFoundWarning,
                stacklevel=2,
            )

    # Otherwise, if no common scopes are authorized, check the username
    else:
        # Test username, available to all scopes
        reddit.username_available(TEST_USERNAME)


def perform_test_request(
    reddit: praw.reddit.Reddit,
    account_key: str,
    scopes: Collection[str],
    *,
    raise_error: bool = True,
) -> bool:
    """Perform a test Reddit request based on the scope to confirm access."""
    # Ideally, simply check the account's identity
    if "*" in scopes or "identity" in scopes:
        scope_check = ScopeCheck.IDENTITY
    # Read an arbitrary thread
    elif "read" in scopes:
        scope_check = ScopeCheck.READ_POST
    # Read an arbitrary wiki page
    elif "wikiread" in scopes:
        scope_check = ScopeCheck.READ_WIKI
    # Otherwise, if no common scopes are authorized, check the username
    else:
        # Test username, available to all scopes
        warning_message = (
            f"Account {account_key!r} scopes ({scopes!r}) did not include"
            f"any typically used for access ({TESTABLE_SCOPES!r})"
        )
        warnings.warn(
            warning_message,
            submanager.exceptions.NoCommonScopesWarning,
            stacklevel=2,
        )

        scope_check = ScopeCheck.USERNAME

    try:
        try_perform_test_request(
            reddit=reddit,
            account_key=account_key,
            scope_check=scope_check,
        )
    except submanager.exceptions.PRAW_AUTHORIZATION_ERRORS as error:
        if not raise_error:
            return False
        raise submanager.exceptions.AccountCheckAuthError(
            account_key=account_key,
            message_pre=(
                f"Authorization error testing scope {scope_check.value!r}"
            ),
            message_post=error,
        ) from error
    except submanager.exceptions.PRAW_REDDIT_ERRORS as error:
        if not raise_error:
            return False
        raise submanager.exceptions.AccountCheckError(
            account_key=account_key,
            message_pre=(
                f"Error testing scope {scope_check.value!r} "
                "(check Reddit's status and your credentials')"
            ),
            message_post=error,
        ) from error

    return True


# ---- Individual account validation ----


def validate_account_offline(
    reddit: praw.reddit.Reddit,
    account_key: str,
    *,
    check_readonly: bool = True,
    raise_error: bool = True,
) -> bool:
    """Validate the passed account without connecting to Reddit."""
    if check_readonly:
        read_only = reddit.read_only
        if read_only or read_only is None:
            if not raise_error:
                return False
            raise submanager.exceptions.RedditReadOnlyError(
                account_key=account_key,
                message_pre="Reddit is read-only due to missing credentials",
                message_post=(
                    "If this is intentional, disable "
                    "`check_readonly` in the config file to skip."
                ),
            )
    return True


def validate_account(
    reddit: praw.reddit.Reddit,
    account_key: str,
    *,
    offline_only: bool = False,
    check_readonly: bool = True,
    raise_error: bool = True,
) -> bool:
    """Check if the Reddit account associated with the object is authorized."""
    # First, do offline validation
    account_valid = validate_account_offline(
        reddit=reddit,
        account_key=account_key,
        check_readonly=check_readonly,
        raise_error=raise_error,
    )
    if not account_valid:
        return False
    if offline_only:
        return True

    # Then, perform a request to get the authorized scopes
    try:
        scopes: set[str] = reddit.auth.scopes()
    except submanager.exceptions.PRAW_REDDIT_ERRORS as error:
        if not raise_error:
            return False
        raise submanager.exceptions.ScopeCheckError(
            account_key=account_key,
            message_pre=(
                "Error attempting to get scopes due to bad auth "
                "credentials or Reddit server issues"
            ),
            message_post=error,
        ) from error
    if not scopes:
        if not raise_error:
            return False
        raise submanager.exceptions.NoAuthorizedScopesError(
            account_key=account_key,
            message_pre=f"The OAUTH token has no authorized scope {scopes!r}",
        )

    # Finally, perform an actual operational test request against a scope
    account_valid = perform_test_request(
        reddit=reddit,
        account_key=account_key,
        scopes=scopes,
        raise_error=raise_error,
    )

    return account_valid


# ---- Top level account validation ----


def validate_accounts(
    accounts: AccountsMap,
    *,
    offline_only: bool = False,
    check_readonly: bool = True,
    raise_error: bool = True,
    verbose: bool = False,
) -> dict[str, bool]:
    """Validate that the passed accounts are authenticated and work."""
    vprint = submanager.utils.output.VerbosePrinter(verbose)

    # For each account, validate it offline and online
    accounts_valid = {}
    for account_key, reddit in accounts.items():
        vprint(f"Validating account {account_key!r}")
        account_valid = validate_account_offline(
            reddit=reddit,
            account_key=account_key,
            check_readonly=check_readonly,
            raise_error=raise_error,
        )
        if account_valid and not offline_only:
            account_valid = validate_account(
                reddit,
                account_key=account_key,
                raise_error=raise_error,
            )
        accounts_valid[account_key] = account_valid
    return accounts_valid
