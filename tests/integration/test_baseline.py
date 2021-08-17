"""Basic integrated smoke tests for the package."""

# Future imports
from __future__ import (
    annotations,
)

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
    found_submodules = {}
    for module_info in pkgutil.walk_packages(search_path):
        full_name = f"{package.__name__}.{module_info.name}"
        found_submodules[full_name] = importlib.import_module(full_name)
        if module_info.ispkg:
            found_submodules.update(import_submodules_recursive(full_name))
    return found_submodules


# ---- Tests ----


def test_import_all() -> None:
    """Test that all modules in the package import successfully."""
    found_submodules = import_submodules_recursive("submanager")

    assert found_submodules
    assert next(iter(found_submodules))
