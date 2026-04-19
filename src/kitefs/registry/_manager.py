"""Registry manager — orchestrates discovery, validation, serialization, and persistence."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kitefs.definitions import FeatureGroup
from kitefs.exceptions import DefinitionError, FeatureGroupNotFoundError, ProviderError, RegistryError
from kitefs.providers.base import StorageProvider
from kitefs.registry._discovery import _discover_definitions
from kitefs.registry._serialization import _deserialize_group, _serialize_group
from kitefs.registry._validation import _validate_definitions


@dataclass(frozen=True)
class ApplyResult:
    """Result of a successful apply() operation.

    registered_groups: sorted tuple of all registered feature group names.
    group_count: total number of registered feature groups.
    """

    registered_groups: tuple[str, ...]
    group_count: int


class RegistryManager:
    """Manages the registry.json lifecycle for a KiteFS project.

    Orchestrates definition discovery, structural validation, serialization,
    persistence via the provider, and lookup queries for SDK operations.
    """

    def __init__(self, provider: StorageProvider, definitions_path: Path) -> None:
        """Initialise with a storage provider and definitions directory path.

        Loads the existing registry from the provider on construction so that
        last_materialized_at values are available for preservation during apply()
        and lookup methods return results immediately without re-reading disk.

        If no registry file exists yet, initialises with an empty registry dict.
        Raises RegistryError if the registry file exists but is unreadable (I/O
        error) or contains invalid JSON.
        """
        self._provider = provider
        self._definitions_path = definitions_path
        self._registry = self._load_registry()

    def _load_registry(self) -> dict:
        """Read and parse the registry from the provider.

        Returns an empty registry dict if the registry file does not exist yet
        (ProviderError with no chained cause — the "not found" case).
        Re-raises as RegistryError if the read fails due to a genuine I/O error
        (ProviderError chained from an OSError — permission denied, disk error, etc.)
        so that real infrastructure failures are not silently swallowed.
        Raises RegistryError if the file exists but contains malformed JSON.
        """
        try:
            raw = self._provider.read_registry()
        except ProviderError as exc:
            # Distinguish "file does not exist yet" from a genuine I/O failure.
            # Providers signal "not found" by raising ProviderError directly (no __cause__).
            # Genuine I/O errors chain the original OSError as __cause__.
            if exc.__cause__ is not None:
                raise RegistryError(
                    f"Registry file could not be read: {exc}. Check file permissions and available disk space."
                ) from exc
            return {"version": "1.0", "feature_groups": {}}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RegistryError(
                f"Registry file contains invalid JSON: {exc}. "
                "Run `kitefs apply` to regenerate it from your definitions."
            ) from exc

    def apply(self) -> "ApplyResult":
        """Discover, validate, serialize, and persist all feature group definitions.

        Full orchestration pipeline:
        1. Discover FeatureGroup instances from the definitions directory.
        2. Validate all groups structurally (all errors collected before raising).
        3. Serialize each group to registry JSON schema format.
        4. Preserve last_materialized_at from the existing registry where present.
        5. Set applied_at to the current UTC timestamp for every group.
        6. Write deterministic JSON via the provider.
        7. Update in-memory registry state and return ApplyResult.

        Raises DefinitionError if any definitions are invalid. The registry file
        remains unchanged when this error is raised.
        Raises ProviderError if the registry cannot be written.
        """
        groups = _discover_definitions(self._definitions_path)
        errors = _validate_definitions(groups)

        if errors:
            raise DefinitionError(
                "Definition validation failed with the following errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        existing_groups: dict[str, dict] = self._registry.get("feature_groups", {})
        now = datetime.now(UTC).isoformat()

        feature_groups: dict[str, dict] = {}
        for group in groups:
            serialized = _serialize_group(group)
            serialized["applied_at"] = now
            # Carry forward last_materialized_at from the previous registry entry.
            # New groups get null; existing groups keep their last materialization time.
            serialized["last_materialized_at"] = existing_groups.get(group.name, {}).get("last_materialized_at")
            feature_groups[group.name] = serialized

        registry: dict = {"version": "1.0", "feature_groups": feature_groups}
        self._provider.write_registry(json.dumps(registry, sort_keys=True, indent=2))
        self._registry = registry

        names = tuple(sorted(feature_groups.keys()))
        return ApplyResult(registered_groups=names, group_count=len(names))

    def get_group(self, name: str) -> FeatureGroup:
        """Return the FeatureGroup for the given name from the in-memory registry.

        Raises FeatureGroupNotFoundError if the group is not registered.
        """
        groups: dict[str, dict] = self._registry.get("feature_groups", {})
        if name not in groups:
            raise FeatureGroupNotFoundError(
                f"Feature group '{name}' not found in registry. Run `kitefs apply` to register your definitions."
            )
        return _deserialize_group(name, groups[name])

    def get_group_entry(self, name: str) -> dict:
        """Return the full registry entry dict for a feature group.

        Unlike get_group(), this returns the raw registry dict including
        runtime fields (applied_at, last_materialized_at) needed by
        describe_feature_group().

        Raises FeatureGroupNotFoundError if the group is not registered.
        """
        groups: dict[str, dict] = self._registry.get("feature_groups", {})
        if name not in groups:
            raise FeatureGroupNotFoundError(
                f"Feature group '{name}' not found in registry. Run `kitefs apply` to register your definitions."
            )
        # Deep copy via JSON round-trip so callers cannot mutate the in-memory registry.
        return json.loads(json.dumps(groups[name]))

    def list_groups(self) -> list[dict]:
        """Return summary dicts for all registered feature groups.

        Each dict contains: name, owner, entity_key (field name), storage_target,
        feature_count.
        """
        groups: dict[str, dict] = self._registry.get("feature_groups", {})
        return [
            {
                "name": data["name"],
                "owner": (data.get("metadata") or {}).get("owner"),
                "entity_key": data["entity_key"]["name"],
                "storage_target": data["storage_target"],
                "feature_count": len(data.get("features", [])),
            }
            for data in groups.values()
        ]

    def group_exists(self, name: str) -> bool:
        """Return True if a feature group with the given name is registered."""
        return name in self._registry.get("feature_groups", {})

    def update_materialized_at(self, group_name: str, timestamp: datetime) -> None:
        """Update last_materialized_at for a group and persist the registry.

        Called by the SDK after a successful materialize() operation.
        Not yet implemented — will be completed in Task 18.
        """
        raise NotImplementedError("update_materialized_at will be implemented in Task 18.")

    def validate_query_params(
        self,
        from_: str,
        select: list[str] | str | dict[str, list[str] | str],
        where: dict[str, dict[str, Any]] | None,
        join: list[str] | None,
        method: str,
    ) -> None:
        """Validate select, where, and join parameters against registered definitions.

        Checks group existence, feature existence, where field/operator validity for
        the given method, join path validity, and the single-join MVP limit.
        method must be 'get_historical_features' or 'get_online_features'.

        Not yet implemented — will be completed in Tasks 14, 16, and 19.
        """
        raise NotImplementedError("validate_query_params will be implemented in Tasks 14, 16, and 19.")
