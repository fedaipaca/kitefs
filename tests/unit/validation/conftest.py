"""Fixtures shared across validation unit tests."""

from __future__ import annotations

import datetime

import pytest

from kitefs.enums import FeatureType, StorageTarget, ValidationMode
from kitefs.registry.parser import describe_feature_group
from kitefs.registry.serializer import build_registry_document
from kitefs.sdk.results import FeatureGroupDescription, FieldSpec, JoinKeySpec, MetadataSpec
from tests.fixtures.definitions import build_town_market_features


@pytest.fixture
def town_market_description() -> FeatureGroupDescription:
    """Return a FeatureGroupDescription for town_market_features via the serializer round-trip.

    Uses the registry serializer + parser so the serialized expect format
    ({"type": "gt", "value": 0}) is what the engine actually receives.
    """
    doc = build_registry_document(
        [build_town_market_features()],
        prior_document={},
        now=datetime.datetime.now(datetime.UTC),
    )
    return describe_feature_group(doc, "town_market_features")


def make_description(
    *,
    entity_key_name: str = "id",
    entity_key_dtype: FeatureType = FeatureType.INTEGER,
    event_timestamp_name: str = "ts",
    features: list[FieldSpec] | None = None,
    join_keys: list[JoinKeySpec] | None = None,
    group_name: str = "test_group",
) -> FeatureGroupDescription:
    """Build a minimal FeatureGroupDescription for targeted unit tests.

    Defaults to a single FLOAT feature named "value" with no expectations.
    """
    return FeatureGroupDescription(
        name=group_name,
        storage_target=StorageTarget.OFFLINE,
        entity_key=FieldSpec(
            name=entity_key_name,
            dtype=entity_key_dtype,
            description=None,
            expect=None,
        ),
        event_timestamp=FieldSpec(
            name=event_timestamp_name,
            dtype=FeatureType.DATETIME,
            description=None,
            expect=None,
        ),
        features=features or [FieldSpec(name="value", dtype=FeatureType.FLOAT, description=None, expect=None)],
        join_keys=join_keys or [],
        ingestion_validation=ValidationMode.ERROR,
        offline_retrieval_validation=ValidationMode.NONE,
        metadata=MetadataSpec(description=None, owner=None, tags={}),
        applied_at=None,
        last_materialized_at=None,
    )
