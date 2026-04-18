"""Registry manager for KiteFS — definition discovery, validation, and registry lifecycle."""

import importlib.util
import sys
from pathlib import Path

from kitefs.definitions import FeatureGroup
from kitefs.exceptions import DefinitionError


def _discover_definitions(definitions_path: Path) -> list[FeatureGroup]:
    """Scan a definitions directory and return all discovered FeatureGroup instances.

    Walks `.py` files in *definitions_path* (non-recursive), dynamically imports
    each one via ``importlib``, and collects module-level attributes that are
    ``FeatureGroup`` instances.

    Import errors are collected — not fail-fast — so the caller sees every
    broken file in a single pass.

    Raises ``DefinitionError`` if any file fails to import or if no
    ``FeatureGroup`` instances are found.
    """
    if not definitions_path.is_dir():
        raise DefinitionError(
            f"Definitions directory '{definitions_path}' does not exist. "
            "Run `kitefs init` to create the project structure."
        )

    py_files = sorted(f for f in definitions_path.iterdir() if f.suffix == ".py" and f.name != "__init__.py")

    errors: list[str] = []
    groups: list[FeatureGroup] = []

    for py_file in py_files:
        module_name = f"kitefs_definitions.{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:  # pragma: no cover — defensive
                errors.append(f"Failed to import definition file '{py_file.name}': could not create module spec.")
                continue
            module = importlib.util.module_from_spec(spec)
            # Temporarily register so relative imports inside the file resolve.
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            finally:
                sys.modules.pop(module_name, None)

            for attr in vars(module).values():
                if isinstance(attr, FeatureGroup):
                    groups.append(attr)
        except Exception as exc:
            errors.append(f"Failed to import definition file '{py_file.name}': {type(exc).__name__}: {exc}")

    if errors:
        raise DefinitionError(
            "Errors occurred while importing definition files:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    if not groups:
        raise DefinitionError(
            f"No feature group definitions found in '{definitions_path}/'. "
            "Create a .py file with a FeatureGroup instance."
        )

    return groups
