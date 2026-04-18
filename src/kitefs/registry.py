"""Registry manager for KiteFS — definition discovery, validation, and registry lifecycle."""

import importlib.util
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kitefs.definitions import (
    EntityKey,
    EventTimestamp,
    Expect,
    Feature,
    FeatureGroup,
    FeatureType,
    JoinKey,
    Metadata,
    StorageTarget,
    ValidationMode,
)
from kitefs.exceptions import DefinitionError, FeatureGroupNotFoundError, ProviderError, RegistryError
from kitefs.providers.base import StorageProvider


@dataclass(frozen=True)
class ApplyResult:
    """Result of a successful apply() operation.

    registered_groups: sorted tuple of all registered feature group names.
    group_count: total number of registered feature groups.
    """

    registered_groups: tuple[str, ...]
    group_count: int


def _serialize_expect(expect: Expect | None) -> list[dict] | None:
    """Convert internal Expect constraints to the registry JSON format.

    Internal: ({"type": "not_null"}, {"type": "gt", "value": 0})
    Registry: [{"not_null": true}, {"gt": 0}]
    """
    if expect is None:
        return None
    result: list[dict] = []
    for constraint in expect._constraints:
        constraint_type = constraint["type"]
        if constraint_type == "not_null":
            result.append({"not_null": True})
        elif constraint_type in ("gt", "gte", "lt", "lte"):
            result.append({constraint_type: constraint["value"]})
        elif constraint_type == "one_of":
            result.append({"one_of": list(constraint["values"])})
    return result or None


def _deserialize_expect(expect_data: list[dict] | None) -> Expect | None:
    """Convert registry JSON expect format back to an internal Expect object."""
    if not expect_data:
        return None
    expect = Expect()
    for constraint in expect_data:
        key = next(iter(constraint))
        if key == "not_null":
            expect = expect.not_null()
        elif key in ("gt", "gte", "lt", "lte"):
            expect = getattr(expect, key)(constraint[key])
        elif key == "one_of":
            expect = expect.one_of(constraint[key])
    return expect


def _serialize_group(group: FeatureGroup) -> dict:
    """Convert a FeatureGroup to the registry JSON schema dict.

    Does not include applied_at or last_materialized_at — those runtime
    fields are added by apply() after serialization.
    """
    return {
        "name": group.name,
        "storage_target": group.storage_target.value,
        "entity_key": {
            "name": group.entity_key.name,
            "dtype": group.entity_key.dtype.value,
            "description": group.entity_key.description,
        },
        "event_timestamp": {
            "name": group.event_timestamp.name,
            "dtype": group.event_timestamp.dtype.value,
            "description": group.event_timestamp.description,
        },
        "features": [
            {
                "name": f.name,
                "dtype": f.dtype.value,
                "description": f.description,
                "expect": _serialize_expect(f.expect),
            }
            for f in group.features
        ],
        "join_keys": [
            {
                "field_name": jk.field_name,
                "referenced_group": jk.referenced_group,
            }
            for jk in group.join_keys
        ],
        "ingestion_validation": group.ingestion_validation.value,
        "offline_retrieval_validation": group.offline_retrieval_validation.value,
        "metadata": {
            "description": group.metadata.description,
            "owner": group.metadata.owner,
            "tags": group.metadata.tags,
        },
    }


def _deserialize_group(name: str, data: dict) -> FeatureGroup:
    """Reconstruct a FeatureGroup from its registry JSON dict.

    Ignores applied_at and last_materialized_at — those are runtime fields
    not part of the definition.
    """
    ek = data["entity_key"]
    et = data["event_timestamp"]

    entity_key = EntityKey(
        name=ek["name"],
        dtype=FeatureType(ek["dtype"]),
        description=ek.get("description"),
    )
    event_timestamp = EventTimestamp(
        name=et["name"],
        dtype=FeatureType(et["dtype"]),
        description=et.get("description"),
    )
    features = [
        Feature(
            name=f["name"],
            dtype=FeatureType(f["dtype"]),
            description=f.get("description"),
            expect=_deserialize_expect(f.get("expect")),
        )
        for f in data.get("features", [])
    ]
    join_keys = [
        JoinKey(
            field_name=jk["field_name"],
            referenced_group=jk["referenced_group"],
        )
        for jk in data.get("join_keys", [])
    ]
    meta = data.get("metadata") or {}
    metadata = Metadata(
        description=meta.get("description"),
        owner=meta.get("owner"),
        tags=meta.get("tags"),
    )
    return FeatureGroup(
        name=name,
        storage_target=StorageTarget(data["storage_target"]),
        entity_key=entity_key,
        event_timestamp=event_timestamp,
        features=features,
        join_keys=join_keys,
        ingestion_validation=ValidationMode(data["ingestion_validation"]),
        offline_retrieval_validation=ValidationMode(data["offline_retrieval_validation"]),
        metadata=metadata,
    )


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


def _validate_definitions(groups: list[FeatureGroup]) -> list[str]:
    """Check a list of feature group definitions against all structural rules.

    Returns a list of error message strings. An empty list means all definitions
    are valid. Collects **all** errors before returning — never fails on the
    first error alone.

    Validation runs in two phases:
    1. Individual group validation (per-group structural checks).
    2. Cross-group validation (uniqueness and join key integrity).
    """
    errors: list[str] = []

    # --- Phase 1: Individual group validation ---
    for group in groups:
        _validate_group(group, errors)

    # --- Phase 2: Cross-group validation ---
    _validate_cross_group(groups, errors)

    return errors


def _validate_group(group: FeatureGroup, errors: list[str]) -> None:
    """Run per-group structural checks, appending any errors found."""
    # EventTimestamp dtype must be DATETIME.
    if group.event_timestamp.dtype != FeatureType.DATETIME:
        errors.append(
            f"Group '{group.name}': EventTimestamp field '{group.event_timestamp.name}' "
            f"must have dtype DATETIME, got {group.event_timestamp.dtype.value}."
        )

    # Feature dtype must be a FeatureType member.
    for feature in group.features:
        if not isinstance(feature.dtype, FeatureType):
            errors.append(
                f"Group '{group.name}': Feature '{feature.name}' has invalid dtype "
                f"'{feature.dtype}'. Supported: STRING, INTEGER, FLOAT, DATETIME."
            )

    # Field names must be unique across entity_key, event_timestamp, and features.
    all_names: list[str] = [
        group.entity_key.name,
        group.event_timestamp.name,
        *(f.name for f in group.features),
    ]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in all_names:
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    for dup in sorted(duplicates):
        errors.append(
            f"Group '{group.name}': Duplicate field name '{dup}' found across "
            "entity_key, event_timestamp, and features."
        )


def _validate_cross_group(groups: list[FeatureGroup], errors: list[str]) -> None:
    """Run cross-group validation checks, appending any errors found."""
    # Duplicate feature group names.
    name_counts = Counter(g.name for g in groups)
    for name, count in sorted(name_counts.items()):
        if count > 1:
            errors.append(f"Duplicate feature group name '{name}' found {count} times.")

    # When names are duplicated, the last group wins — acceptable because
    # duplicate names are already caught above.
    group_map: dict[str, FeatureGroup] = {g.name: g for g in groups}

    for group in groups:
        for join_key in group.join_keys:
            ref_name = join_key.referenced_group

            # Referenced group must exist.
            if ref_name not in group_map:
                errors.append(f"Group '{group.name}': Join key references non-existent group '{ref_name}'.")
                continue

            ref_group = group_map[ref_name]

            # Join key field_name must match the referenced group's entity_key.name.
            if join_key.field_name != ref_group.entity_key.name:
                errors.append(
                    f"Group '{group.name}': Join key field '{join_key.field_name}' "
                    f"must match entity key name '{ref_group.entity_key.name}' of "
                    f"referenced group '{ref_name}'. Rename the field to "
                    f"'{ref_group.entity_key.name}'."
                )

            # Join key field must exist in the base group.
            base_field_dtype = _find_field_dtype(group, join_key.field_name)
            if base_field_dtype is None:
                errors.append(
                    f"Group '{group.name}': Join key field '{join_key.field_name}' "
                    f"does not exist as an entity_key or feature in this group."
                )
                continue

            # Join key type compatibility: the field in the base group must have
            # the same dtype as the referenced group's entity key.
            ref_ek_dtype = ref_group.entity_key.dtype
            if base_field_dtype != ref_ek_dtype:
                errors.append(
                    f"Group '{group.name}': Join key field '{join_key.field_name}' "
                    f"has dtype {base_field_dtype.value} but entity key "
                    f"'{ref_group.entity_key.name}' of referenced group "
                    f"'{ref_name}' has dtype {ref_ek_dtype.value}."
                )


def _find_field_dtype(group: FeatureGroup, field_name: str) -> FeatureType | None:
    """Look up a field's dtype in a group by checking entity_key then features."""
    if group.entity_key.name == field_name:
        return group.entity_key.dtype
    for feature in group.features:
        if feature.name == field_name:
            return feature.dtype
    return None


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
