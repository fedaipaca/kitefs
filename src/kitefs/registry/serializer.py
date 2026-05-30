"""Registry artifact builder: serialize FeatureGroups into the registry JSON document."""

from __future__ import annotations

import datetime
from typing import Any

from kitefs.constants import DATETIME_FMT
from kitefs.definitions import FeatureGroup


def _serialize_expect(expect: Any) -> list[dict[str, Any]] | None:
    """Serialize an Expect instance to the registry constraint list format, or None."""
    if expect is None:
        return None
    result: list[dict[str, Any]] = []
    for op, value in expect._constraints:
        if op == "not_null":
            result.append({"type": "not_null"})
        elif op == "is_in":
            serialized_values = [v.strftime(DATETIME_FMT) if isinstance(v, datetime.datetime) else v for v in value]
            result.append({"type": op, "value": serialized_values})
        else:
            v = value.strftime(DATETIME_FMT) if isinstance(v := value, datetime.datetime) else value
            result.append({"type": op, "value": v})
    return result if result else None


def _serialize_feature_group(
    group: FeatureGroup,
    *,
    applied_at: datetime.datetime,
    last_materialized_at: str | None,
) -> dict[str, Any]:
    features = sorted(group.features, key=lambda f: f.name)
    join_keys = sorted(group.join_keys, key=lambda jk: jk.name)

    metadata = group.metadata
    metadata_dict: dict[str, Any] = {
        "description": metadata.description if metadata else None,
        "owner": metadata.owner if metadata else None,
        "tags": metadata.tags if metadata else {},
    }

    return {
        "applied_at": applied_at.strftime(DATETIME_FMT),
        "entity_key": {
            "description": group.entity_key.description,
            "dtype": group.entity_key.dtype.value,
            "name": group.entity_key.name,
        },
        "event_timestamp": {
            "description": group.event_timestamp.description,
            "dtype": group.event_timestamp.dtype.value,
            "name": group.event_timestamp.name,
        },
        "features": [
            {
                "description": f.description,
                "dtype": f.dtype.value,
                "expect": _serialize_expect(f.expect),
                "name": f.name,
            }
            for f in features
        ],
        "ingestion_validation": group.ingestion_validation.value,
        "join_keys": [
            {
                "dtype": jk.dtype.value,
                "name": jk.name,
                "referenced_group": jk.referenced_group,
            }
            for jk in join_keys
        ],
        "last_materialized_at": last_materialized_at,
        "metadata": metadata_dict,
        "name": group.name,
        "offline_retrieval_validation": group.offline_retrieval_validation.value,
        "storage_target": group.storage_target.value,
    }


def build_registry_document(
    groups: list[FeatureGroup],
    *,
    prior_document: dict[str, Any],
    now: datetime.datetime,
) -> dict[str, Any]:
    """Serialize groups into the full registry document, preserving last_materialized_at."""
    prior_groups = prior_document.get("feature_groups", {})
    prior_lm: dict[str, str | None] = {name: entry.get("last_materialized_at") for name, entry in prior_groups.items()}

    feature_groups = {
        group.name: _serialize_feature_group(
            group,
            applied_at=now,
            last_materialized_at=prior_lm.get(group.name),
        )
        for group in sorted(groups, key=lambda g: g.name)
    }

    return {"feature_groups": feature_groups}


__all__ = ["build_registry_document"]
