from __future__ import annotations

import datetime
import re
from typing import Any

from kitefs.enums import FeatureType, StorageTarget, ValidationMode
from kitefs.errors import DefinitionError, format_actionable

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_NUMERIC_TYPES = (int, float, datetime.datetime)

_ENTITY_KEY_ALLOWED = frozenset({FeatureType.STRING, FeatureType.INTEGER})
_EVENT_TS_ALLOWED = frozenset({FeatureType.DATETIME})
_JOIN_KEY_ALLOWED = frozenset({FeatureType.STRING, FeatureType.INTEGER})


def _require_identifier(name: str, context: str) -> None:
    """Raise DefinitionError if name does not match the CON-009 identifier regex."""
    if not _IDENTIFIER_RE.match(name):
        raise DefinitionError(
            format_actionable(
                field=name,
                problem=f"{context} name must be a valid identifier",
                next_step="use a name matching ^[a-zA-Z_][a-zA-Z0-9_]*$",
            )
        )


class Expect:
    """Fluent builder for per-feature value constraints checked during validation."""

    def __init__(self) -> None:
        self._constraints: list[tuple[str, Any]] = []

    def not_null(self) -> Expect:
        self._constraints.append(("not_null", None))
        return self

    def _require_numeric(self, op: str, value: Any) -> None:
        if not isinstance(value, _NUMERIC_TYPES):
            raise DefinitionError(
                format_actionable(
                    problem=f"'{op}' threshold must be int, float, or datetime, got {type(value).__name__!r}",
                    next_step="pass an int, float, or datetime.datetime value",
                )
            )

    def gt(self, value: int | float | datetime.datetime) -> Expect:
        self._require_numeric("gt", value)
        self._constraints.append(("gt", value))
        return self

    def gte(self, value: int | float | datetime.datetime) -> Expect:
        self._require_numeric("gte", value)
        self._constraints.append(("gte", value))
        return self

    def lt(self, value: int | float | datetime.datetime) -> Expect:
        self._require_numeric("lt", value)
        self._constraints.append(("lt", value))
        return self

    def lte(self, value: int | float | datetime.datetime) -> Expect:
        self._require_numeric("lte", value)
        self._constraints.append(("lte", value))
        return self

    def is_in(self, values: list[str | int | float | datetime.datetime]) -> Expect:
        if not values:
            raise DefinitionError(
                format_actionable(
                    problem="'is_in' values list must not be empty",
                    next_step="provide at least one allowed value",
                )
            )
        self._constraints.append(("is_in", list(values)))
        return self


class EntityKey:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        description: str | None = None,
    ) -> None:
        _require_identifier(name, "EntityKey")
        if dtype not in _ENTITY_KEY_ALLOWED:
            raise DefinitionError(
                format_actionable(
                    field=name,
                    problem=f"EntityKey dtype must be STRING or INTEGER, got {dtype.value}",
                    next_step="use one of STRING, INTEGER",
                )
            )
        self.name = name
        self.dtype = dtype
        self.description = description


class EventTimestamp:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType = FeatureType.DATETIME,
        description: str | None = None,
    ) -> None:
        _require_identifier(name, "EventTimestamp")
        if dtype not in _EVENT_TS_ALLOWED:
            raise DefinitionError(
                format_actionable(
                    field=name,
                    problem=f"EventTimestamp dtype must be DATETIME, got {dtype.value}",
                    next_step="use DATETIME or omit dtype (defaults to DATETIME)",
                )
            )
        self.name = name
        self.dtype = dtype
        self.description = description


class Feature:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        description: str | None = None,
        expect: Expect | None = None,
    ) -> None:
        _require_identifier(name, "Feature")
        self.name = name
        self.dtype = dtype
        self.description = description
        self.expect = expect


class JoinKey:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        referenced_group: str,
        description: str | None = None,
    ) -> None:
        _require_identifier(name, "JoinKey")
        if dtype not in _JOIN_KEY_ALLOWED:
            raise DefinitionError(
                format_actionable(
                    field=name,
                    problem=f"JoinKey dtype must be STRING or INTEGER, got {dtype.value}",
                    next_step="use one of STRING, INTEGER",
                )
            )
        if not referenced_group.strip():
            raise DefinitionError(
                format_actionable(
                    field=name,
                    problem="JoinKey referenced_group must not be empty",
                    next_step="provide the name of the referenced feature group",
                )
            )
        self.name = name
        self.dtype = dtype
        self.referenced_group = referenced_group
        self.description = description


class Metadata:
    def __init__(
        self,
        *,
        description: str,
        owner: str,
        tags: dict[str, str] | None = None,
    ) -> None:
        if not description.strip():
            raise DefinitionError(
                format_actionable(
                    problem="Metadata description must not be empty",
                    next_step="provide a non-empty description string",
                )
            )
        if not owner.strip():
            raise DefinitionError(
                format_actionable(
                    problem="Metadata owner must not be empty",
                    next_step="provide a non-empty owner string",
                )
            )
        self.description = description
        self.owner = owner
        self.tags: dict[str, str] = tags if tags is not None else {}


class FeatureGroup:
    def __init__(
        self,
        *,
        name: str,
        storage_target: StorageTarget,
        entity_key: EntityKey,
        event_timestamp: EventTimestamp,
        features: list[Feature],
        join_keys: list[JoinKey] | None = None,
        ingestion_validation: ValidationMode = ValidationMode.ERROR,
        offline_retrieval_validation: ValidationMode = ValidationMode.NONE,
        metadata: Metadata | None = None,
    ) -> None:
        if not _IDENTIFIER_RE.match(name):
            raise DefinitionError(
                format_actionable(
                    field=name,
                    problem=f"FeatureGroup name '{name}' must be a valid identifier",
                    next_step="use a name matching ^[a-zA-Z_][a-zA-Z0-9_]*$",
                )
            )
        if not features:
            raise DefinitionError(
                format_actionable(
                    group=name,
                    problem="FeatureGroup must have at least one feature",
                    next_step="add at least one Feature to the features list",
                )
            )
        effective_join_keys = join_keys or []
        if len(effective_join_keys) > 1:
            raise DefinitionError(
                format_actionable(
                    group=name,
                    problem=f"FeatureGroup may have at most one join_key, got {len(effective_join_keys)}",
                    next_step="reduce join_keys to one entry or remove it",
                )
            )
        all_names = [
            entity_key.name,
            event_timestamp.name,
            *[jk.name for jk in effective_join_keys],
            *[f.name for f in features],
        ]
        seen: set[str] = set()
        for field_name in all_names:
            if field_name in seen:
                raise DefinitionError(
                    format_actionable(
                        group=name,
                        field=field_name,
                        problem=f"duplicate field name '{field_name}' in FeatureGroup",
                        next_step=(
                            "ensure all field names (entity key, event timestamp, join keys, features) are unique"
                        ),
                    )
                )
            seen.add(field_name)

        self.name = name
        self.storage_target = storage_target
        self.entity_key = entity_key
        self.event_timestamp = event_timestamp
        self.features = features
        self.join_keys = effective_join_keys
        self.ingestion_validation = ingestion_validation
        self.offline_retrieval_validation = offline_retrieval_validation
        self.metadata = metadata


__all__ = [
    "EntityKey",
    "EventTimestamp",
    "Expect",
    "Feature",
    "FeatureGroup",
    "JoinKey",
    "Metadata",
]
