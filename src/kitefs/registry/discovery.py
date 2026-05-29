"""Definition discovery: import *.py files from the definitions directory and collect FeatureGroups."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from kitefs.definitions import FeatureGroup
from kitefs.errors import DefinitionDiscoveryError, format_actionable


def discover_feature_groups(definitions_dir: Path) -> list[FeatureGroup]:
    """Import every *.py file in definitions_dir and return all module-level FeatureGroup instances.

    Files are processed in sorted order for determinism. Raises DefinitionDiscoveryError
    if any file fails to import, or if no FeatureGroup instances are found.
    """
    groups: list[FeatureGroup] = []
    seen_ids: set[int] = set()

    for file_path in sorted(definitions_dir.glob("*.py")):
        module_name = f"kitefs._discovered.{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise DefinitionDiscoveryError(
                format_actionable(
                    setting=str(file_path),
                    problem="could not load module spec for definition file",
                    next_step="ensure the file is a valid Python source file and re-run apply",
                )
            )
        module = types.ModuleType(module_name)
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as exc:
            raise DefinitionDiscoveryError(
                format_actionable(
                    setting=str(file_path),
                    problem=f"failed to import definition file: {exc!r}",
                    next_step="fix the import error and re-run apply",
                )
            ) from exc

        for obj in vars(module).values():
            if isinstance(obj, FeatureGroup) and id(obj) not in seen_ids:
                groups.append(obj)
                seen_ids.add(id(obj))

        # Clean up the module from sys.modules to avoid cross-run pollution.
        sys.modules.pop(module_name, None)

    if not groups:
        raise DefinitionDiscoveryError(
            format_actionable(
                problem=f"no FeatureGroup definitions discovered under {definitions_dir}",
                next_step="declare at least one FeatureGroup in feature_store/definitions/*.py",
            )
        )

    return groups


__all__ = ["discover_feature_groups"]
