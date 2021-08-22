"""Validate basic connectivity to Reddit."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
from typing import (
    Collection,
)

# Third party imports
import requests
import requests.exceptions
from typing_extensions import (
    Final,
)

# Local imports
import submanager.exceptions
from submanager.constants import (
    REDDIT_BASE_URL,
    USER_AGENT,
)

REQUEST_TIMEOUT_S: Final[float] = 5


def get_reddit_oauth_scopes(
    scopes: Collection[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Get metadata on the OAUTH scopes offered by the Reddit API."""
    # Set up the request for scopes
    scopes_endpoint = "/api/v1/scopes"
    scopes_endpoint_url = REDDIT_BASE_URL + scopes_endpoint
    headers = {"User-Agent": USER_AGENT}
    query_params = {}
    if scopes:
        query_params["scopes"] = scopes

    # Make and process the request
    response = requests.get(
        scopes_endpoint_url,
        params=query_params,
        headers=headers,
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    response_json: dict[str, dict[str, str]] = response.json()
    return response_json


def check_reddit_connectivity(raise_error: bool = True) -> bool:
    """Check if Sub Manager is able to contact Reddit at all."""
    try:
        get_reddit_oauth_scopes()
    except submanager.exceptions.REQUESTS_CONNECTIVITY_ERROS as error:
        if not raise_error:
            return False
        raise submanager.exceptions.RedditNetworkError(
            message=(
                "Couldn't connect to Reddit at all; "
                "check your internet connection"
            ),
            message_post=error,
        ) from error
    except requests.exceptions.HTTPError as error:
        if not raise_error:
            return False
        raise submanager.exceptions.RedditHTTPError(
            message=(
                "Received a HTTP error attempting to test connectivity "
                "with Reddit; check if their servers are down"
            ),
            message_post=error,
        ) from error

    return True
