"""Test that the validate-config command validates the configuration."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
from typing import (
    Dict,
    Optional,
    Tuple,
    Type,
    Union,
)

# Third party imports
import pytest
from typing_extensions import (
    Final,
)

# Local imports
import submanager.enums
import submanager.exceptions
import submanager.models.config
from submanager.types import (
    ConfigDict,
)
from tests.functional.conftest import (
    CONFIG_EXTENSIONS_BAD,
    CONFIG_EXTENSIONS_GOOD,
    CONFIG_PATHS_OFFLINE,
    CONFIG_PATHS_ONLINE,
    RunAndCheckCLICallable,
    RunAndCheckDebugCallable,
)

# ---- Types ----

RequestValues = Union[str, bool, None]
RequestTuple = Union[Tuple[ConfigDict, RequestValues], ConfigDict]
ExpectedTuple = Tuple[
    str,
    Optional[Type[submanager.exceptions.SubManagerUserError]],
]
ParamConfigs = Dict[str, Tuple[RequestTuple, ExpectedTuple]]


# ---- Constants ----

# pylint: disable = consider-using-namedtuple-or-dataclass

PSEUDORANDOM_STRING: Final[str] = "izouashbutyzyep"
INT_VALUE: Final[int] = 42

# CLI constants
VALIDATE_COMMAND: Final[str] = "validate-config"
MINIMAL_ARGS: Final[list[str]] = ["", "--minimal"]
INCLUDE_DISABLED_ARGS: Final[list[str]] = ["", "--include-disabled"]
OFFLINE_ONLY_ARG: Final[str] = "--offline-only"
OFFLINE_ONLY_ARGS: Final = [
    OFFLINE_ONLY_ARG,
    pytest.param("", marks=[pytest.mark.online]),
]
OFFLINE_ONLY_ARGS_SLOW: Final = [
    OFFLINE_ONLY_ARG,
    pytest.param("", marks=[pytest.mark.slow, pytest.mark.online]),
]

# Offline validation param configs
VALIDATION_EXPECTED: Final[ExpectedTuple] = (
    "validat",
    submanager.exceptions.ConfigValidationError,
)
ACCOUNT_EXPECTED: Final[ExpectedTuple] = (
    "account",
    submanager.exceptions.AccountConfigError,
)
READONLY_EXPECTED: Final[ExpectedTuple] = (
    "read",
    submanager.exceptions.RedditReadOnlyError,
)

BAD_VALIDATE_OFFLINE_PARAMS: Final[ParamConfigs] = {
    "non_existent_key": (
        {PSEUDORANDOM_STRING: PSEUDORANDOM_STRING},
        VALIDATION_EXPECTED,
    ),
    "account_int": (
        {"context_default": {"account": INT_VALUE}},
        VALIDATION_EXPECTED,
    ),
    "account_nomatch": (
        {"context_default": {"account": PSEUDORANDOM_STRING}},
        VALIDATION_EXPECTED,
    ),
    "subreddit_int": (
        {"context_default": {"subreddit": INT_VALUE}},
        VALIDATION_EXPECTED,
    ),
    "subreddit_missing": (
        {"context_default": {"subreddit": None}},
        VALIDATION_EXPECTED,
    ),
    "clientid_missing": (
        {"accounts": {"muskbot": {"config": {"client_id": None}}}},
        ACCOUNT_EXPECTED,
    ),
    "sitename_nomatch": (
        {
            "accounts": {
                "muskrat": {"config": {"site_name": PSEUDORANDOM_STRING}},
            },
        },
        ACCOUNT_EXPECTED,
    ),
    "token_missing": (
        {"accounts": {"muskbot": {"config": {"refresh_token": None}}}},
        READONLY_EXPECTED,
    ),
    "pw_missing": (
        {"accounts": {"muskrat": {"config": {"password": None}}}},
        READONLY_EXPECTED,
    ),
}

# Onlne validation param configs
NON_ACCESSIBLE_PAGE: Final[str] = "non_accessible_page"
NON_MOD_SUBREDDIT: Final[str] = "SubManagerTesting2"
NON_SUPPORTED_WIDGET: Final[str] = "Bad Type Widget"
NON_WRITEABLE_PAGE: Final[str] = "non_writable_page"
NON_WRITEABLE_WIDGET: Final[str] = "Test Widget"
THREAD_ID_LINK: Final[str] = "oy6ju3"
THREAD_ID_NOT_OP: Final[str] = "owu3jn"

BAD_VALIDATE_ONLINE_PARAMS: Final[ParamConfigs] = {
    "placebo": (
        ({}, True),
        ("succe", None),
    ),
    "client_id_bad": (
        (
            {
                "accounts": {
                    "testbot": {"config": {"client_id": PSEUDORANDOM_STRING}},
                },
            },
            True,
        ),
        ("scope", submanager.exceptions.ScopeCheckError),
    ),
    "subreddit_notfound": (
        (
            {"context_default": {"subreddit": PSEUDORANDOM_STRING}},
            "sync_manager.items.menus.targets.old_reddit_menu",
        ),
        ("subreddit", submanager.exceptions.SubredditNotFoundError),
    ),
    "thread_source_notfound": (
        (
            {
                "thread_manager": {
                    "items": {
                        "cycle_thread": {
                            "source": {"endpoint_name": PSEUDORANDOM_STRING},
                        },
                    },
                },
            },
            "thread_manager.items.cycle_thread",
        ),
        ("found", submanager.exceptions.RedditObjectNotFoundError),
    ),
    "menu_notfound": (
        (
            {
                "sync_manager": {
                    "items": {
                        "menus": {
                            "targets": {
                                "new_reddit_menu": {
                                    "context": {
                                        "subreddit": NON_MOD_SUBREDDIT,
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.menus.targets.new_reddit_menu",
        ),
        ("create", submanager.exceptions.RedditObjectNotFoundError),
    ),
    "thread_notfound": (
        (
            {
                "sync_manager": {
                    "items": {
                        "sidebar_thread": {
                            "targets": {
                                "thread_target": {
                                    "endpoint_name": PSEUDORANDOM_STRING,
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.sidebar_thread.targets.thread_target",
        ),
        ("found", submanager.exceptions.RedditObjectNotFoundError),
    ),
    "thread_notop": (
        (
            {
                "sync_manager": {
                    "items": {
                        "sidebar_thread": {
                            "targets": {
                                "thread_target": {
                                    "endpoint_name": THREAD_ID_NOT_OP,
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.sidebar_thread.targets.thread_target",
        ),
        ("account", submanager.exceptions.NotOPError),
    ),
    "thread_wrong_type": (
        (
            {
                "sync_manager": {
                    "items": {
                        "sidebar_thread": {
                            "targets": {
                                "thread_target": {
                                    "endpoint_name": THREAD_ID_LINK,
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.sidebar_thread.targets.thread_target",
        ),
        ("link", submanager.exceptions.PostTypeError),
    ),
    "widget_notfound": (
        (
            {
                "sync_manager": {
                    "items": {
                        "sidebar_thread": {
                            "targets": {
                                "new_reddit_widget": {
                                    "endpoint_name": PSEUDORANDOM_STRING,
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.sidebar_thread.targets.new_reddit_widget",
        ),
        ("found", submanager.exceptions.RedditObjectNotFoundError),
    ),
    "widget_wrong_type": (
        (
            {
                "sync_manager": {
                    "items": {
                        "sidebar_thread": {
                            "targets": {
                                "new_reddit_widget": {
                                    "endpoint_name": NON_SUPPORTED_WIDGET,
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.sidebar_thread.targets.new_reddit_widget",
        ),
        ("type", submanager.exceptions.WidgetTypeError),
    ),
    "widget_notwriteable": (
        (
            {
                "sync_manager": {
                    "items": {
                        "sidebar_thread": {
                            "targets": {
                                "new_reddit_widget": {
                                    "endpoint_name": NON_WRITEABLE_WIDGET,
                                    "context": {
                                        "subreddit": NON_MOD_SUBREDDIT,
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.sidebar_thread.targets.new_reddit_widget",
        ),
        ("mod", submanager.exceptions.NotAModError),
    ),
    "wiki_notfound_source": (
        (
            {
                "sync_manager": {
                    "items": {
                        "cross_sub_sync": {
                            "source": {"endpoint_name": PSEUDORANDOM_STRING},
                        },
                    },
                },
            },
            "sync_manager.items.cross_sub_sync.targets.index_clone",
        ),
        ("found", submanager.exceptions.RedditObjectNotFoundError),
    ),
    "wiki_notaccessible_source": (
        (
            {
                "sync_manager": {
                    "items": {
                        "cross_sub_sync": {
                            "source": {"endpoint_name": NON_ACCESSIBLE_PAGE},
                        },
                    },
                },
            },
            "sync_manager.items.cross_sub_sync.targets.index_clone",
        ),
        ("access", submanager.exceptions.RedditObjectNotAccessibleError),
    ),
    "wiki_notfound_target": (
        (
            {
                "sync_manager": {
                    "items": {
                        "disabled_sync_item": {
                            "targets": {
                                "non_existent": {
                                    "endpoint_name": PSEUDORANDOM_STRING,
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.disabled_sync_item.targets.non_existent",
        ),
        ("found", submanager.exceptions.RedditObjectNotFoundError),
    ),
    "wiki_notaccessible_target": (
        (
            {},
            "sync_manager.items.disabled_sync_item.targets.non_existent",
        ),
        ("access", submanager.exceptions.RedditObjectNotAccessibleError),
    ),
    "wiki_notwriteable_target": (
        (
            {
                "sync_manager": {
                    "items": {
                        "disabled_sync_item": {
                            "targets": {
                                "non_existent": {
                                    "endpoint_name": NON_WRITEABLE_PAGE,
                                    "context": {
                                        "subreddit": NON_MOD_SUBREDDIT,
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "sync_manager.items.disabled_sync_item.targets.non_existent",
        ),
        ("edit", submanager.exceptions.WikiPagePermissionError),
    ),
}


# ---- Tests ----


@pytest.mark.parametrize("include_disabled", INCLUDE_DISABLED_ARGS)
@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
def test_generated_error(
    run_and_check_cli: RunAndCheckCLICallable,
    example_config: submanager.models.config.ConfigPaths,
    minimal: str,
    include_disabled: str,
) -> None:
    """Test that the generated config validates false."""
    error_type: type[submanager.exceptions.SubManagerUserError]
    if minimal:
        error_type = submanager.exceptions.AccountConfigError
    else:
        error_type = submanager.exceptions.ConfigDefaultError

    run_and_check_cli(
        cli_args=[
            VALIDATE_COMMAND,
            OFFLINE_ONLY_ARG,
            minimal,
            include_disabled,
        ],
        config_paths=example_config,
        check_text="account" if minimal else "default",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=error_type,
    )


@pytest.mark.parametrize("temp_config_dir", ["", "missing_dir"], indirect=True)
@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
def test_config_not_found(
    run_and_check_cli: RunAndCheckCLICallable,
    temp_config_paths: submanager.models.config.ConfigPaths,
    minimal: str,
) -> None:
    """Test that the config not being found validates false."""
    run_and_check_cli(
        cli_args=[VALIDATE_COMMAND, OFFLINE_ONLY_ARG, minimal],
        config_paths=temp_config_paths,
        check_text="not found",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigNotFoundError,
    )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize(
    "temp_config_paths",
    CONFIG_EXTENSIONS_GOOD + CONFIG_EXTENSIONS_BAD,
    indirect=True,
)
def test_config_empty_error(
    run_and_check_cli: RunAndCheckCLICallable,
    empty_config: submanager.models.config.ConfigPaths,
    minimal: str,
) -> None:
    """Test that validating a config file with an unknown extension errors."""
    extension = empty_config.static.suffix.lstrip(".")
    check_error: type[submanager.exceptions.SubManagerUserError]
    if extension == "json":
        check_text = "pars"
        check_error = submanager.exceptions.ConfigParsingError
    elif extension in CONFIG_EXTENSIONS_GOOD:
        check_text = "empty"
        check_error = submanager.exceptions.ConfigEmptyError
    else:
        check_text = "extension"
        check_error = submanager.exceptions.ConfigExtensionError
    run_and_check_cli(
        cli_args=[VALIDATE_COMMAND, OFFLINE_ONLY_ARG, minimal],
        config_paths=empty_config,
        check_text=check_text,
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=check_error,
    )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("temp_config_paths", ["json"], indirect=True)
def test_config_list_error(
    run_and_check_cli: RunAndCheckCLICallable,
    list_config: submanager.models.config.ConfigPaths,
    minimal: str,
) -> None:
    """Test that a config file with the wrong data structure fails validate."""
    run_and_check_cli(
        cli_args=[VALIDATE_COMMAND, OFFLINE_ONLY_ARG, minimal],
        config_paths=list_config,
        check_text="structure",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigDataTypeError,
    )


@pytest.mark.parametrize("include_disabled", INCLUDE_DISABLED_ARGS)
@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_OFFLINE, indirect=True)
def test_valid_offline(
    run_and_check_cli: RunAndCheckCLICallable,
    file_config: submanager.models.config.ConfigPaths,
    minimal: str,
    include_disabled: str,
) -> None:
    """Test that the test configs validate true in offline mode."""
    run_and_check_cli(
        cli_args=[
            VALIDATE_COMMAND,
            OFFLINE_ONLY_ARG,
            minimal,
            include_disabled,
        ],
        config_paths=file_config,
        check_text="succe",
    )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_OFFLINE, indirect=True)
def test_parsing_error(
    run_and_check_cli: RunAndCheckCLICallable,
    file_config: submanager.models.config.ConfigPaths,
    minimal: str,
) -> None:
    """Test that config files with an invalid file format validate false."""
    with open(file_config.static, encoding="utf-8") as config_file_read:
        config_file_text = config_file_read.read()
    config_file_text = config_file_text.replace('"', "", 1)
    with open(
        file_config.static,
        mode="w",
        encoding="utf-8",
        newline="\n",
    ) as config_file_write:
        config_file_write.write(config_file_text)

    run_and_check_cli(
        cli_args=[VALIDATE_COMMAND, OFFLINE_ONLY_ARG, minimal],
        config_paths=file_config,
        check_text="pars",
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.ConfigParsingError,
    )


@pytest.mark.parametrize("minimal", MINIMAL_ARGS)
@pytest.mark.parametrize(
    ("modified_config", "check_vars"),
    list(BAD_VALIDATE_OFFLINE_PARAMS.values()),
    ids=list(BAD_VALIDATE_OFFLINE_PARAMS.keys()),
    indirect=["modified_config"],
)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_OFFLINE, indirect=True)
def test_value_error(
    run_and_check_cli: RunAndCheckCLICallable,
    modified_config: submanager.models.config.ConfigPaths,
    check_vars: ExpectedTuple,
    minimal: str,
) -> None:
    """Test that config files with a bad value validate false."""
    check_text, check_error = check_vars
    cli_args = [VALIDATE_COMMAND, OFFLINE_ONLY_ARG, minimal]
    if minimal and (
        check_error is None
        or (check_error == submanager.exceptions.RedditReadOnlyError)
    ):
        run_and_check_cli(
            cli_args=cli_args,
            config_paths=modified_config,
            check_text="succe",
        )
    else:
        run_and_check_cli(
            cli_args=cli_args,
            config_paths=modified_config,
            check_text=check_text,
            check_code=submanager.enums.ExitCode.ERROR_USER,
            check_error=check_error,
        )


def test_debug_error(
    run_and_check_debug: RunAndCheckDebugCallable,
) -> None:
    """Test that --debug allows the error to bubble up and dump traceback."""
    run_and_check_debug([VALIDATE_COMMAND, OFFLINE_ONLY_ARG])


@pytest.mark.parametrize("include_disabled", INCLUDE_DISABLED_ARGS)
@pytest.mark.parametrize("offline_only", OFFLINE_ONLY_ARGS_SLOW)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ONLINE, indirect=True)
def test_valid_online(
    run_and_check_cli: RunAndCheckCLICallable,
    file_config: submanager.models.config.ConfigPaths,
    offline_only: str,
    include_disabled: str,
) -> None:
    """Test that the test configs validate true in offline mode."""
    should_fail = bool(include_disabled and not offline_only)
    run_and_check_cli(
        cli_args=[VALIDATE_COMMAND, offline_only, include_disabled],
        config_paths=file_config,
        check_text="access" if should_fail else "succe",
        check_exits=should_fail,
        check_code=submanager.enums.ExitCode.ERROR_USER,
        check_error=submanager.exceptions.RedditObjectNotAccessibleError,
    )


@pytest.mark.parametrize("offline_only", OFFLINE_ONLY_ARGS)
@pytest.mark.parametrize(
    ("modified_config", "check_vars"),
    list(BAD_VALIDATE_ONLINE_PARAMS.values()),
    ids=list(BAD_VALIDATE_ONLINE_PARAMS.keys()),
    indirect=["modified_config"],
)
@pytest.mark.parametrize("file_config", CONFIG_PATHS_ONLINE, indirect=True)
def test_online_error(
    run_and_check_cli: RunAndCheckCLICallable,
    modified_config: submanager.models.config.ConfigPaths,
    check_vars: ExpectedTuple,
    offline_only: str,
) -> None:
    """Test that config files that produce Reddit errors validate false."""
    check_text, check_error = check_vars
    cli_args = [VALIDATE_COMMAND, offline_only]
    if offline_only or check_error is None:
        run_and_check_cli(
            cli_args=cli_args,
            config_paths=modified_config,
            check_text="succe",
        )
    else:
        run_and_check_cli(
            cli_args=cli_args,
            config_paths=modified_config,
            check_text=check_text,
            check_code=submanager.enums.ExitCode.ERROR_USER,
            check_error=check_error,
        )
