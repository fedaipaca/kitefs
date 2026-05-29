"""Unit tests for kitefs.cli.render — CLI presentation helpers."""

from __future__ import annotations

import datetime
import json

from kitefs.cli.render import render_describe, render_list
from kitefs.enums import FeatureType, StorageTarget, ValidationMode
from kitefs.sdk.results import (
    FeatureGroupDescription,
    FeatureGroupSummary,
    FieldSpec,
    MetadataSpec,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_NOW = datetime.datetime(2026, 5, 29, 12, 0, 0, tzinfo=datetime.UTC)
_NOW_STR = "2026-05-29T12:00:00.000000Z"


def _make_summary(name: str, **kw) -> FeatureGroupSummary:
    defaults = dict(
        owner="data-science-team",
        description=None,
        entity_key="town_id",
        storage_target=StorageTarget.OFFLINE_AND_ONLINE,
        feature_count=1,
    )
    return FeatureGroupSummary(name=name, **{**defaults, **kw})


def _make_description() -> FeatureGroupDescription:
    return FeatureGroupDescription(
        name="town_market_features",
        storage_target=StorageTarget.OFFLINE_AND_ONLINE,
        entity_key=FieldSpec(name="town_id", dtype=FeatureType.INTEGER, description=None, expect=None),
        event_timestamp=FieldSpec(name="event_timestamp", dtype=FeatureType.DATETIME, description=None, expect=None),
        features=[
            FieldSpec(
                name="avg_price_per_sqm",
                dtype=FeatureType.FLOAT,
                description=None,
                expect=[{"type": "not_null"}, {"type": "gt", "value": 0}],
            )
        ],
        join_keys=[],
        ingestion_validation=ValidationMode.ERROR,
        offline_retrieval_validation=ValidationMode.NONE,
        metadata=MetadataSpec(
            description="Town-level market stats",
            owner="data-science-team",
            tags={},
        ),
        applied_at=_NOW,
        last_materialized_at=None,
    )


# ---------------------------------------------------------------------------
# render_list — text
# ---------------------------------------------------------------------------


class TestRenderListText:
    """render_list(..., as_json=False) produces a human-readable table."""

    def test_empty_returns_sentinel(self) -> None:
        """Empty summaries list returns the 'No feature groups registered.' sentinel."""
        result = render_list([], as_json=False)
        assert result == "No feature groups registered."

    def test_header_row_present(self) -> None:
        """Output contains column headers."""
        result = render_list([_make_summary("town_market_features")], as_json=False)
        assert "NAME" in result
        assert "OWNER" in result
        assert "STORAGE TARGET" in result
        assert "FEATURES" in result

    def test_name_and_storage_target_in_output(self) -> None:
        """Group name and storage target appear in the rendered text."""
        result = render_list(
            [_make_summary("town_market_features", storage_target=StorageTarget.OFFLINE_AND_ONLINE)],
            as_json=False,
        )
        assert "town_market_features" in result
        assert "OFFLINE_AND_ONLINE" in result

    def test_multiple_rows(self) -> None:
        """Multiple groups each appear as a row."""
        summaries = [
            _make_summary("listing_features", storage_target=StorageTarget.OFFLINE, entity_key="listing_id"),
            _make_summary("town_market_features"),
        ]
        result = render_list(summaries, as_json=False)
        assert "listing_features" in result
        assert "town_market_features" in result


# ---------------------------------------------------------------------------
# render_list — json
# ---------------------------------------------------------------------------


class TestRenderListJson:
    """render_list(..., as_json=True) produces a valid JSON array."""

    def test_empty_returns_empty_array_string(self) -> None:
        """Empty summaries list returns '[]'."""
        assert render_list([], as_json=True) == "[]"

    def test_valid_json(self) -> None:
        """Output is parseable JSON."""
        result = render_list([_make_summary("town_market_features")], as_json=True)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_json_fields(self) -> None:
        """Each JSON object contains the contract fields."""
        result = render_list([_make_summary("town_market_features")], as_json=True)
        obj = json.loads(result)[0]
        assert obj["name"] == "town_market_features"
        assert obj["owner"] == "data-science-team"
        assert obj["entity_key"] == "town_id"
        assert obj["storage_target"] == "OFFLINE_AND_ONLINE"
        assert obj["feature_count"] == 1

    def test_storage_target_is_string_value(self) -> None:
        """storage_target is serialized as the enum string value, not the enum repr."""
        result = render_list([_make_summary("x", storage_target=StorageTarget.OFFLINE)], as_json=True)
        obj = json.loads(result)[0]
        assert obj["storage_target"] == "OFFLINE"


# ---------------------------------------------------------------------------
# render_describe — text
# ---------------------------------------------------------------------------


class TestRenderDescribeText:
    """render_describe(..., as_json=False) produces a human-readable description block."""

    def test_name_present(self) -> None:
        """Group name appears in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "town_market_features" in result

    def test_storage_target_present(self) -> None:
        """Storage target appears in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "OFFLINE_AND_ONLINE" in result

    def test_entity_key_present(self) -> None:
        """Entity key name appears in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "town_id" in result

    def test_feature_name_present(self) -> None:
        """Feature name appears in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "avg_price_per_sqm" in result

    def test_expect_constraints_present(self) -> None:
        """Constraint names appear in text output."""
        result = render_describe(_make_description(), as_json=False)
        assert "not_null" in result


# ---------------------------------------------------------------------------
# render_describe — json
# ---------------------------------------------------------------------------


class TestRenderDescribeJson:
    """render_describe(..., as_json=True) produces a JSON object matching the registry entry shape."""

    def test_valid_json(self) -> None:
        """Output is parseable JSON."""
        result = render_describe(_make_description(), as_json=True)
        assert isinstance(json.loads(result), dict)

    def test_entity_key_name(self) -> None:
        """entity_key.name in JSON is 'town_id'."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert data["entity_key"]["name"] == "town_id"

    def test_storage_target_value(self) -> None:
        """storage_target in JSON is the enum string value."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert data["storage_target"] == "OFFLINE_AND_ONLINE"

    def test_feature_name_present(self) -> None:
        """features array contains avg_price_per_sqm."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        feature_names = [f["name"] for f in data["features"]]
        assert "avg_price_per_sqm" in feature_names

    def test_entity_key_has_no_expect_key(self) -> None:
        """entity_key dict in JSON omits the 'expect' key (matches registry entry shape)."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert "expect" not in data["entity_key"]

    def test_event_timestamp_has_no_expect_key(self) -> None:
        """event_timestamp dict in JSON omits the 'expect' key."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert "expect" not in data["event_timestamp"]

    def test_feature_expect_in_json(self) -> None:
        """Feature constraints are present in the features array."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        f = data["features"][0]
        assert f["expect"] == [{"type": "not_null"}, {"type": "gt", "value": 0}]

    def test_applied_at_formatted_as_string(self) -> None:
        """applied_at datetime is re-serialized to an ISO string."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert data["applied_at"] == _NOW_STR

    def test_last_materialized_at_none(self) -> None:
        """last_materialized_at=None renders as JSON null."""
        data = json.loads(render_describe(_make_description(), as_json=True))
        assert data["last_materialized_at"] is None
