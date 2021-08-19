"""Miscellaneous utility functions and classes."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import copy
import time
from typing import (
    Any,
    Callable,
    Collection,
    Mapping,
    MutableMapping,
    TypeVar,
)

# Constants and types
KeyType = TypeVar("KeyType")


# ---- General utilities ----


def sleep_for_interval(sleep_interval: float) -> None:
    """Sleep for the designated interval in small increments."""
    time_left_s = sleep_interval
    while True:
        time_to_sleep_s = min((time_left_s, 1))
        time.sleep(time_to_sleep_s)
        time_left_s -= 1
        if time_left_s <= 0:
            return


# ---- Dictionary handling code ----


def _process_items_inner(
    dict_toprocess: MutableMapping[KeyType, Any],
    fn_torun: Callable[..., Any],
    *,
    fn_kwargs: Mapping[str, Any],
    keys_match: Collection[str] | None,
) -> None:
    """Inner function to call recursively to handle dict items."""
    for key, value in dict_toprocess.items():
        if isinstance(value, MutableMapping):
            _process_items_inner(
                dict_toprocess=value,
                fn_torun=fn_torun,
                fn_kwargs=fn_kwargs,
                keys_match=keys_match,
            )
        elif keys_match is None or key in keys_match:
            dict_toprocess[key] = fn_torun(value, **fn_kwargs)


def process_items_recursive(
    dict_toprocess: MutableMapping[KeyType, Any],
    fn_torun: Callable[..., Any],
    *,
    fn_kwargs: Mapping[str, Any] | None = None,
    keys_match: Collection[str] | None = None,
    inplace: bool = False,
) -> MutableMapping[KeyType, Any]:
    """Run the passed function for every matching key in the dictionary."""
    if fn_kwargs is None:
        fn_kwargs = {}
    if not inplace:
        dict_toprocess = copy.deepcopy(dict_toprocess)

    _process_items_inner(
        dict_toprocess=dict_toprocess,
        fn_torun=fn_torun,
        fn_kwargs=fn_kwargs,
        keys_match=keys_match,
    )
    return dict_toprocess


def update_recursive(
    base: MutableMapping[KeyType, Any],
    update: MutableMapping[KeyType, Any],
    *,
    inplace: bool = False,
) -> MutableMapping[KeyType, Any]:
    """Recursively update the given base dict from another dict."""
    if not inplace:
        base = copy.deepcopy(base)
    for update_key, update_value in update.items():
        base_value = base.get(update_key, {})
        # If the base value is not a dict, simply copy it from the update dict
        if not isinstance(base_value, MutableMapping):
            base[update_key] = update_value
        # If both the bsae value and update value are dicts, recurse into them
        elif isinstance(update_value, MutableMapping):
            base[update_key] = update_recursive(base_value, update_value)
        # If the base balue is a dict but the update value is not, replace it
        else:
            base[update_key] = update_value
    return base
