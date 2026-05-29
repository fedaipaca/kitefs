"""Registry document parser: deserialize the registry JSON document into SDK result types.

This is the inverse of serializer.py — it reads the persisted document produced by
build_registry_document/write and reconstructs typed dataclasses without any I/O.
"""

from __future__ import annotations

import datetime
from typing import Any

from kitefs.enums import FeatureType, StorageTarget, ValidationMode
from kitefs.errors import FeatureGroupNotFoundError, format_actionable
from kitefs.registry.serializer import _DATETIME_FMT
from kitefs.sdk.results import (
    FeatureGroupDescription,
    FeatureGroupSummary,
    FieldSpec,
    JoinKeySpec,
    MetadataSpec,
)


def _parse_dt(value: str | None) -> datetime.datetime | None:
    """Parse an ISO registry datetime string to datetime, or return None."""
    if value is None:
        return None
    return datetime.datetime.strptime(value, _DATETIME_FMT).replace(tzinfo=datetime.UTC)


def _parse_field(entry: dict[str, Any], *, include_expect: bool) -> FieldSpec:
    """Build a FieldSpec from a serialized field dict (entity_key, event_timestamp, or feature)."""
    return FieldSpec(
        name=entry["name"],
        dtype=FeatureType(entry["dtype"]),
        description=entry.get("description"),
        expect=entry.get("expect") if include_expect else None,
    )


def summarize_registry(document: dict[str, Any]) -> list[FeatureGroupSummary]:
    """Return one FeatureGroupSummary per registered group, sorted alphabetically by name.

    Returns an empty list when the registry contains no feature groups.
    """
    groups: dict[str, Any] = document.get("feature_groups", {})
    summaries = []
    for entry in groups.values():
        meta = entry.get("metadata") or {}
        summaries.append(
            FeatureGroupSummary(
                name=entry["name"],
                owner=meta.get("owner"),
                description=meta.get("description"),
                entity_key=entry["entity_key"]["name"],
                storage_target=StorageTarget(entry["storage_target"]),
                feature_count=len(entry.get("features", [])),
            )
        )
    return sorted(summaries, key=lambda s: s.name)


def describe_feature_group(document: dict[str, Any], name: str) -> FeatureGroupDescription:
    """Return the full FeatureGroupDescription for the named group.

    Raises FeatureGroupNotFoundError if name is not present, including the sorted
    list of valid registered names in the message.
    """
    groups: dict[str, Any] = document.get("feature_groups", {})
    if name not in groups:
        valid = sorted(groups.keys())
        raise FeatureGroupNotFoundError(
            format_actionable(
                group=name,
                problem=f"feature group not found in registry; registered groups: {valid}",
                next_step="run 'kitefs apply' or pick one of the registered groups",
            )
        )

    entry = groups[name]
    meta = entry.get("metadata") or {}

    return FeatureGroupDescription(
        name=entry["name"],
        storage_target=StorageTarget(entry["storage_target"]),
        entity_key=_parse_field(entry["entity_key"], include_expect=False),
        event_timestamp=_parse_field(entry["event_timestamp"], include_expect=False),
        features=[_parse_field(f, include_expect=True) for f in entry.get("features", [])],
        join_keys=[
            JoinKeySpec(
                name=jk["name"],
                dtype=FeatureType(jk["dtype"]),
                referenced_group=jk["referenced_group"],
            )
            for jk in entry.get("join_keys", [])
        ],
        ingestion_validation=ValidationMode(entry["ingestion_validation"]),
        offline_retrieval_validation=ValidationMode(entry["offline_retrieval_validation"]),
        metadata=MetadataSpec(
            description=meta.get("description"),
            owner=meta.get("owner"),
            tags=meta.get("tags") or {},
        ),
        applied_at=_parse_dt(entry.get("applied_at")),
        last_materialized_at=_parse_dt(entry.get("last_materialized_at")),
    )


__all__ = ["describe_feature_group", "summarize_registry"]
