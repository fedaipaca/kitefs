"""SDK entry point — orchestrates all KiteFS operations through a single class."""

import json
from pathlib import Path
from typing import TypeVar

from kitefs.config import load_config
from kitefs.exceptions import ConfigurationError, FeatureGroupNotFoundError
from kitefs.providers.factory import create_provider
from kitefs.registry import ApplyResult, RegistryManager

_T = TypeVar("_T", list[dict], dict)


class FeatureStore:
    """Root SDK class that wires configuration, provider, and managers.

    Instantiate with an explicit project root or let the constructor walk
    up from the current working directory to find ``kitefs.yaml``.
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        """Initialise the feature store from a KiteFS project directory.

        If *project_root* is provided, use it directly. Otherwise walk up
        from ``cwd`` to locate ``kitefs.yaml``.
        """
        resolved_root = self._resolve_project_root(project_root)

        config = load_config(resolved_root)
        provider = create_provider(config)
        self._registry_manager = RegistryManager(provider, config.definitions_path)

    def apply(self) -> ApplyResult:
        """Register all feature group definitions into the registry."""
        return self._registry_manager.apply()

    def list_feature_groups(
        self,
        format: str | None = None,
        target: str | None = None,
    ) -> list[dict] | str:
        """Return a summary of all registered feature groups.

        Parameters match the documented API contract: default returns
        ``list[dict]``, ``format="json"`` returns a JSON string,
        ``target`` writes JSON to a file and returns the target path.
        """
        summaries = self._registry_manager.list_groups()
        return self._format_output(summaries, format=format, target=target)

    def describe_feature_group(
        self,
        name: str,
        format: str | None = None,
        target: str | None = None,
    ) -> dict | str:
        """Return the full definition of a specific registered feature group.

        Raises FeatureGroupNotFoundError if *name* is not in the registry.
        """
        try:
            entry = self._registry_manager.get_group_entry(name)
        except FeatureGroupNotFoundError:
            raise FeatureGroupNotFoundError(
                f"Feature group '{name}' not found in registry. Run `kitefs list` to see registered groups."
            ) from None
        return self._format_output(entry, format=format, target=target)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_output(
        data: _T,
        *,
        format: str | None,
        target: str | None,
    ) -> _T | str:
        """Apply the target-first, then format=json, then structured-return precedence."""
        if target is not None:
            Path(target).write_text(
                json.dumps(data, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            return str(target)
        if format == "json":
            return json.dumps(data, sort_keys=True, indent=2)
        return data

    @staticmethod
    def _resolve_project_root(project_root: str | Path | None) -> Path:
        """Resolve the project root to a concrete directory containing kitefs.yaml."""
        if project_root is not None:
            root = Path(project_root).resolve()
            if not (root / "kitefs.yaml").exists():
                raise ConfigurationError("No KiteFS project found. Run `kitefs init` to create one.")
            return root

        # Walk upward from cwd until kitefs.yaml is found.
        current = Path.cwd().resolve()
        while True:
            if (current / "kitefs.yaml").exists():
                return current
            parent = current.parent
            if parent == current:
                # Reached filesystem root without finding a project.
                raise ConfigurationError("No KiteFS project found. Run `kitefs init` to create one.")
            current = parent
