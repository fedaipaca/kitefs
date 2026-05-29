"""Unit tests for the registry artifact builder."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from kitefs.definitions import (
    EntityKey,
    EventTimestamp,
    Expect,
    Feature,
    FeatureGroup,
    FeatureType,
    Metadata,
    StorageTarget,
)
from kitefs.registry.serializer import build_registry_document
from tests.fixtures.definitions import build_listing_features, build_town_market_features

_NOW = datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC)
_NOW_STR = "2026-05-29T12:00:00.000000Z"


def _build_doc(groups, *, prior=None):
    return build_registry_document(groups, prior_document=prior or {"feature_groups": {}}, now=_NOW)


class TestTopLevelShape:
    """build_registry_document produces correct top-level structure."""

    def test_has_feature_groups_key(self) -> None:
        """Output always has a 'feature_groups' key."""
        doc = _build_doc([build_town_market_features()])
        assert "feature_groups" in doc

    def test_group_names_are_keys(self) -> None:
        """Both reference groups appear as keys in feature_groups."""
        doc = _build_doc([build_listing_features(), build_town_market_features()])
        assert set(doc["feature_groups"]) == {"listing_features", "town_market_features"}

    def test_groups_sorted_alphabetically(self) -> None:
        """Groups appear in alphabetical order."""
        doc = _build_doc([build_listing_features(), build_town_market_features()])
        assert list(doc["feature_groups"]) == ["listing_features", "town_market_features"]


class TestAppliedAt:
    """applied_at is set to the injected now value."""

    def test_applied_at_matches_now(self) -> None:
        """applied_at serializes the injected datetime as the UTC format string."""
        doc = _build_doc([build_town_market_features()])
        assert doc["feature_groups"]["town_market_features"]["applied_at"] == _NOW_STR

    def test_applied_at_format(self) -> None:
        """applied_at uses YYYY-MM-DDTHH:MM:SS.ffffffZ format."""
        doc = _build_doc([build_town_market_features()])
        val = doc["feature_groups"]["town_market_features"]["applied_at"]
        assert val.endswith("Z")
        assert len(val) == 27  # "YYYY-MM-DDTHH:MM:SS.ffffffZ"


class TestLastMaterializedAt:
    """last_materialized_at is null initially and preserved from prior registry."""

    def test_null_when_no_prior(self) -> None:
        """last_materialized_at is None when the prior registry has no entry for the group."""
        doc = _build_doc([build_town_market_features()])
        assert doc["feature_groups"]["town_market_features"]["last_materialized_at"] is None

    def test_preserved_from_prior_registry(self) -> None:
        """last_materialized_at carries over when the group existed in the prior registry."""
        prior_ts = "2026-05-01T00:00:00.000000Z"
        prior = {
            "feature_groups": {
                "town_market_features": {
                    "last_materialized_at": prior_ts,
                    "applied_at": "2026-04-01T00:00:00.000000Z",
                }
            }
        }
        doc = _build_doc([build_town_market_features()], prior=prior)
        assert doc["feature_groups"]["town_market_features"]["last_materialized_at"] == prior_ts

    def test_not_preserved_for_removed_group(self) -> None:
        """A group absent from the new definitions has its last_materialized_at discarded."""
        prior = {"feature_groups": {"old_group": {"last_materialized_at": "2026-05-01T00:00:00.000000Z"}}}
        doc = _build_doc([build_town_market_features()], prior=prior)
        assert "old_group" not in doc["feature_groups"]


class TestFeaturesSortedAlphabetically:
    """features list is sorted by name before serialization."""

    def test_listing_features_sorted(self) -> None:
        """listing_features has four features; they appear in sorted order."""
        doc = _build_doc([build_listing_features()])
        names = [f["name"] for f in doc["feature_groups"]["listing_features"]["features"]]
        assert names == sorted(names)
        assert names == ["build_year", "net_area", "number_of_rooms", "sold_price"]


class TestJoinKeys:
    """join_keys contains the correct referenced_group and is sorted."""

    def test_join_key_referenced_group(self) -> None:
        """listing_features join_key references town_market_features."""
        doc = _build_doc([build_listing_features(), build_town_market_features()])
        jk = doc["feature_groups"]["listing_features"]["join_keys"][0]
        assert jk["referenced_group"] == "town_market_features"

    def test_no_join_keys_is_empty_list(self) -> None:
        """town_market_features has no join keys; serialized as []."""
        doc = _build_doc([build_town_market_features()])
        assert doc["feature_groups"]["town_market_features"]["join_keys"] == []


class TestExpectSerialization:
    """Expect constraints are serialized to the registry constraint list format."""

    def test_null_expect(self) -> None:
        """A feature with no expect produces null in the registry."""
        group = FeatureGroup(
            name="g",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name="value", dtype=FeatureType.FLOAT, expect=None)],
        )
        doc = _build_doc([group])
        assert doc["feature_groups"]["g"]["features"][0]["expect"] is None

    def test_not_null_constraint(self) -> None:
        """not_null constraint serializes to {"type": "not_null"} with no value field."""
        group = FeatureGroup(
            name="g",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().not_null())],
        )
        doc = _build_doc([group])
        constraints = doc["feature_groups"]["g"]["features"][0]["expect"]
        assert constraints == [{"type": "not_null"}]

    def test_gt_constraint(self) -> None:
        """gt constraint carries a value field."""
        group = FeatureGroup(
            name="g",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name="v", dtype=FeatureType.FLOAT, expect=Expect().gt(0))],
        )
        doc = _build_doc([group])
        constraints = doc["feature_groups"]["g"]["features"][0]["expect"]
        assert {"type": "gt", "value": 0} in constraints

    def test_is_in_constraint(self) -> None:
        """is_in constraint carries a list value field."""
        group = FeatureGroup(
            name="g",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name="v", dtype=FeatureType.STRING, expect=Expect().is_in(["a", "b"]))],
        )
        doc = _build_doc([group])
        constraints = doc["feature_groups"]["g"]["features"][0]["expect"]
        assert constraints == [{"type": "is_in", "value": ["a", "b"]}]

    def test_multiple_constraints_ordering(self) -> None:
        """Multiple constraints appear in the order they were declared."""
        group = FeatureGroup(
            name="g",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name="v", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0).lte(100))],
        )
        doc = _build_doc([group])
        constraints = doc["feature_groups"]["g"]["features"][0]["expect"]
        assert constraints == [{"type": "not_null"}, {"type": "gt", "value": 0}, {"type": "lte", "value": 100}]


class TestMetadata:
    """metadata is serialized with nulls for absent fields and correct tags."""

    def test_metadata_none_produces_null_fields(self) -> None:
        """FeatureGroup with no Metadata produces description=null, owner=null, tags={}."""
        group = FeatureGroup(
            name="g",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name="v", dtype=FeatureType.FLOAT)],
            metadata=None,
        )
        doc = _build_doc([group])
        meta = doc["feature_groups"]["g"]["metadata"]
        assert meta == {"description": None, "owner": None, "tags": {}}

    def test_metadata_with_tags(self) -> None:
        """Present Metadata serializes all fields correctly."""
        group = FeatureGroup(
            name="g",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts"),
            features=[Feature(name="v", dtype=FeatureType.FLOAT)],
            metadata=Metadata(
                description="desc",
                owner="team",
                tags={"env": "prod"},
            ),
        )
        doc = _build_doc([group])
        meta = doc["feature_groups"]["g"]["metadata"]
        assert meta == {"description": "desc", "owner": "team", "tags": {"env": "prod"}}


class TestDeterministicJSON:
    """The serialized document is deterministic (same input → same bytes)."""

    def test_roundtrip_is_stable(self) -> None:
        """Calling build_registry_document twice with the same inputs produces identical output."""
        groups = [build_listing_features(), build_town_market_features()]
        doc1 = _build_doc(groups)
        doc2 = _build_doc(groups)
        assert json.dumps(doc1, sort_keys=True, indent=2) == json.dumps(doc2, sort_keys=True, indent=2)
