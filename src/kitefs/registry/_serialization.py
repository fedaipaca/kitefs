"""Registry serialization — convert between FeatureGroup and registry JSON."""

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
