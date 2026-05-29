"""Unit tests for kitefs.registry.parser — registry document deserialization."""

from __future__ import annotations

import datetime

import pytest

from kitefs.enums import FeatureType, StorageTarget, ValidationMode
from kitefs.errors import FeatureGroupNotFoundError
from kitefs.registry.parser import describe_feature_group, summarize_registry

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_NOW_STR = "2026-05-29T12:00:00.000000Z"
_NOW_DT = datetime.datetime(2026, 5, 29, 12, 0, 0, tzinfo=datetime.UTC)

_TOWN_MARKET_ENTRY = {
    "applied_at": _NOW_STR,
    "entity_key": {"description": None, "dtype": "INTEGER", "name": "town_id"},
    "event_timestamp": {"description": None, "dtype": "DATETIME", "name": "event_timestamp"},
    "features": [
        {
            "description": None,
            "dtype": "FLOAT",
            "expect": [{"type": "not_null"}, {"type": "gt", "value": 0}],
            "name": "avg_price_per_sqm",
        }
    ],
    "ingestion_validation": "ERROR",
    "join_keys": [],
    "last_materialized_at": None,
    "metadata": {"description": "Town-level market stats", "owner": "data-science-team", "tags": {}},
    "name": "town_market_features",
    "offline_retrieval_validation": "NONE",
    "storage_target": "OFFLINE_AND_ONLINE",
}

_LISTING_ENTRY = {
    "applied_at": _NOW_STR,
    "entity_key": {"description": None, "dtype": "INTEGER", "name": "listing_id"},
    "event_timestamp": {"description": None, "dtype": "DATETIME", "name": "sold_at"},
    "features": [
        {"description": None, "dtype": "INTEGER", "expect": None, "name": "net_area"},
    ],
    "ingestion_validation": "ERROR",
    "join_keys": [
        {"dtype": "INTEGER", "name": "town_id", "referenced_group": "town_market_features"},
    ],
    "last_materialized_at": None,
    "metadata": {"description": None, "owner": "data-science-team", "tags": {}},
    "name": "listing_features",
    "offline_retrieval_validation": "NONE",
    "storage_target": "OFFLINE",
}

_TWO_GROUP_DOCUMENT = {
    "feature_groups": {
        "town_market_features": _TOWN_MARKET_ENTRY,
        "listing_features": _LISTING_ENTRY,
    }
}


# ---------------------------------------------------------------------------
# summarize_registry
# ---------------------------------------------------------------------------


class TestSummarizeRegistry:
    """summarize_registry builds FeatureGroupSummary objects from the registry document."""

    def test_empty_registry_returns_empty_list(self) -> None:
        """An empty feature_groups dict produces an empty list."""
        result = summarize_registry({"feature_groups": {}})
        assert result == []

    def test_result_sorted_alphabetically(self) -> None:
        """Summaries are returned sorted by name regardless of dict insertion order."""
        result = summarize_registry(_TWO_GROUP_DOCUMENT)
        assert [s.name for s in result] == ["listing_features", "town_market_features"]

    def test_summary_fields_from_entry(self) -> None:
        """Summary fields map correctly from a registry entry."""
        result = summarize_registry({"feature_groups": {"town_market_features": _TOWN_MARKET_ENTRY}})
        assert len(result) == 1
        s = result[0]
        assert s.name == "town_market_features"
        assert s.owner == "data-science-team"
        assert s.description == "Town-level market stats"
        assert s.entity_key == "town_id"
        assert s.storage_target == StorageTarget.OFFLINE_AND_ONLINE
        assert s.feature_count == 1

    def test_metadata_none_produces_none_owner_and_description(self) -> None:
        """Entries with null metadata fields yield None owner/description on the summary."""
        result = summarize_registry({"feature_groups": {"listing_features": _LISTING_ENTRY}})
        s = result[0]
        assert s.owner == "data-science-team"
        assert s.description is None

    def test_storage_target_offline(self) -> None:
        """OFFLINE storage_target string is correctly parsed to the enum."""
        result = summarize_registry({"feature_groups": {"listing_features": _LISTING_ENTRY}})
        assert result[0].storage_target == StorageTarget.OFFLINE

    def test_feature_count_from_features_list(self) -> None:
        """feature_count is the length of the features list in the entry."""
        result = summarize_registry({"feature_groups": {"listing_features": _LISTING_ENTRY}})
        assert result[0].feature_count == 1


# ---------------------------------------------------------------------------
# describe_feature_group
# ---------------------------------------------------------------------------


class TestDescribeFeatureGroup:
    """describe_feature_group builds a FeatureGroupDescription from a registry entry."""

    def test_raises_when_name_not_found(self) -> None:
        """FeatureGroupNotFoundError is raised when the group name is absent."""
        with pytest.raises(FeatureGroupNotFoundError):
            describe_feature_group(_TWO_GROUP_DOCUMENT, "neighborhood_features")

    def test_not_found_error_contains_target_name(self) -> None:
        """Error message includes the requested group name."""
        with pytest.raises(FeatureGroupNotFoundError) as exc_info:
            describe_feature_group(_TWO_GROUP_DOCUMENT, "neighborhood_features")
        assert "neighborhood_features" in str(exc_info.value)

    def test_not_found_error_lists_valid_names(self) -> None:
        """Error message lists all valid registered names."""
        with pytest.raises(FeatureGroupNotFoundError) as exc_info:
            describe_feature_group(_TWO_GROUP_DOCUMENT, "neighborhood_features")
        msg = str(exc_info.value)
        assert "listing_features" in msg
        assert "town_market_features" in msg

    def test_top_level_fields(self) -> None:
        """Top-level scalar fields are correctly parsed."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "town_market_features")
        assert desc.name == "town_market_features"
        assert desc.storage_target == StorageTarget.OFFLINE_AND_ONLINE
        assert desc.ingestion_validation == ValidationMode.ERROR
        assert desc.offline_retrieval_validation == ValidationMode.NONE

    def test_entity_key_parsed(self) -> None:
        """entity_key is parsed to FieldSpec with no expect."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "town_market_features")
        ek = desc.entity_key
        assert ek.name == "town_id"
        assert ek.dtype == FeatureType.INTEGER
        assert ek.description is None
        assert ek.expect is None

    def test_event_timestamp_parsed(self) -> None:
        """event_timestamp is parsed to FieldSpec with no expect."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "town_market_features")
        et = desc.event_timestamp
        assert et.name == "event_timestamp"
        assert et.dtype == FeatureType.DATETIME
        assert et.expect is None

    def test_feature_field_spec_with_expect(self) -> None:
        """Feature FieldSpec includes the expect constraint list."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "town_market_features")
        assert len(desc.features) == 1
        f = desc.features[0]
        assert f.name == "avg_price_per_sqm"
        assert f.dtype == FeatureType.FLOAT
        assert f.expect == [{"type": "not_null"}, {"type": "gt", "value": 0}]

    def test_feature_with_null_expect(self) -> None:
        """Feature with expect=None in registry yields expect=None on FieldSpec."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "listing_features")
        assert desc.features[0].expect is None

    def test_join_keys_parsed(self) -> None:
        """join_keys are parsed to JoinKeySpec."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "listing_features")
        assert len(desc.join_keys) == 1
        jk = desc.join_keys[0]
        assert jk.name == "town_id"
        assert jk.dtype == FeatureType.INTEGER
        assert jk.referenced_group == "town_market_features"

    def test_empty_join_keys(self) -> None:
        """Groups with no join keys yield an empty list."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "town_market_features")
        assert desc.join_keys == []

    def test_metadata_parsed(self) -> None:
        """Metadata fields are parsed into MetadataSpec."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "town_market_features")
        assert desc.metadata.owner == "data-science-team"
        assert desc.metadata.description == "Town-level market stats"
        assert desc.metadata.tags == {}

    def test_applied_at_parsed_to_datetime(self) -> None:
        """applied_at ISO string is converted to a UTC-aware datetime."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "town_market_features")
        assert desc.applied_at == _NOW_DT

    def test_last_materialized_at_none(self) -> None:
        """last_materialized_at=null in registry yields None on the description."""
        desc = describe_feature_group(_TWO_GROUP_DOCUMENT, "town_market_features")
        assert desc.last_materialized_at is None

    def test_last_materialized_at_parsed_when_present(self) -> None:
        """last_materialized_at ISO string is converted to a UTC-aware datetime when set."""
        entry = {**_TOWN_MARKET_ENTRY, "last_materialized_at": _NOW_STR}
        doc = {"feature_groups": {"town_market_features": entry}}
        desc = describe_feature_group(doc, "town_market_features")
        assert desc.last_materialized_at == _NOW_DT
