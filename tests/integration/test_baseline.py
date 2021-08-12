"""Basic integrated smoke tests for the package."""

# Future imports
from __future__ import annotations

# Standard library imports
import importlib
import pkgutil
from types import (
    ModuleType,
)


# ---- Helper functions ----


def import_submodules_recursive(
    package: ModuleType | str,
) -> dict[str, ModuleType]:
    """Import the submodules of the package, recursively down the tree."""
    if isinstance(package, str):
        package = importlib.import_module(package)
    if not package.__spec__:
        raise ImportError("Package must have a valid spec")
    search_path = package.__spec__.submodule_search_locations
    results = {}
    for module_info in pkgutil.walk_packages(search_path):
        full_name = f"{package.__name__}.{module_info.name}"
        results[full_name] = importlib.import_module(full_name)
        if module_info.ispkg:
            results.update(import_submodules_recursive(full_name))
    return results


# ---- Tests ----


def test_import_all() -> None:
    """Test that all modules in the package import successfully."""
    results = import_submodules_recursive("submanager")

    assert results
    assert next(iter(results))
