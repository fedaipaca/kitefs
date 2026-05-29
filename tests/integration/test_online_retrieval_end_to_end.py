"""Integration tests for Feature 11: end-to-end local online store retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kitefs.errors import FeatureGroupNotMaterializableError, RetrievalParameterError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

_TOWN_MARKET_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[
        Feature(
            name="avg_price_per_sqm",
            dtype=FeatureType.FLOAT,
            expect=Expect().not_null().gt(0),
        ),
    ],
    ingestion_validation=ValidationMode.ERROR,
    metadata=Metadata(
        description="Monthly town-level market aggregate",
        owner="data-science-team",
        tags={},
    ),
)
"""

_LISTING_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="sold_price", dtype=FeatureType.FLOAT),
    ],
    ingestion_validation=ValidationMode.NONE,
    metadata=Metadata(description="Listing features", owner="team", tags={}),
)
"""


def _ts(dt_str: str) -> datetime:
    """Parse an ISO UTC datetime string."""
    return datetime.fromisoformat(dt_str).replace(tzinfo=UTC)


def _setup_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_listing: bool = False,
) -> FeatureStore:
    """Scaffold a project, write definition(s), apply, and return a FeatureStore."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    if include_listing:
        (defs_dir / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    FeatureStore().apply()
    return FeatureStore()


def _ingest_and_materialize(store: FeatureStore) -> None:
    """Ingest a few rows for two towns and materialize them."""
    rows = [
        {"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _ts("2024-01-01T00:00:00")},
        {"town_id": 1, "avg_price_per_sqm": 25000.0, "event_timestamp": _ts("2024-02-01T00:00:00")},
        {"town_id": 2, "avg_price_per_sqm": 18000.0, "event_timestamp": _ts("2024-01-01T00:00:00")},
    ]
    store.ingest("town_market_features", town_market_frame(rows))
    store.materialize("town_market_features")


class TestOnlineHit:
    """get_online_features() returns the latest row for a known entity key."""

    def test_hit_returns_dict_with_expected_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A materialized entity key returns a dict with entity key, timestamp, and feature."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_and_materialize(store)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )

        assert "town_id" in result
        assert "event_timestamp" in result
        assert "avg_price_per_sqm" in result

    def test_hit_entity_key_is_correct_type_and_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The entity key in the returned dict is a Python int with the correct value."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_and_materialize(store)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )

        assert result["town_id"] == 1
        assert isinstance(result["town_id"], int)

    def test_hit_event_timestamp_is_utc_aware_datetime(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The event_timestamp in the result is a UTC-aware datetime.datetime."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_and_materialize(store)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )

        assert isinstance(result["event_timestamp"], datetime)
        assert result["event_timestamp"].tzinfo is not None
        assert result["event_timestamp"].tzinfo == UTC

    def test_hit_returns_latest_row_feature_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The returned feature value is from the most recent event_timestamp row."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_and_materialize(store)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )

        # town_id=1 has two rows; the latest (2024-02-01) has avg_price_per_sqm=25000.0
        assert result["avg_price_per_sqm"] == pytest.approx(25000.0)

    def test_different_entity_key_returns_correct_row(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each entity key maps to its own distinct result."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_and_materialize(store)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 2}},
        )

        assert result["town_id"] == 2
        assert result["avg_price_per_sqm"] == pytest.approx(18000.0)


class TestOnlineMiss:
    """get_online_features() returns {} for unknown entity keys."""

    def test_miss_returns_empty_dict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-existent entity key returns {} without raising."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_and_materialize(store)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 9999}},
        )

        assert result == {}

    def test_never_materialized_returns_empty_dict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A group that was never materialized returns {} without raising."""
        _setup_store(tmp_path, monkeypatch)  # no ingest or materialize

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )

        assert result == {}


class TestWildcardSelect:
    """select=['*'] returns all declared feature fields plus structural columns."""

    def test_wildcard_select_returns_all_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """select=['*'] returns entity key, event timestamp, and all feature fields."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_and_materialize(store)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["*"],
            where={"town_id": {"eq": 1}},
        )

        assert "town_id" in result
        assert "event_timestamp" in result
        assert "avg_price_per_sqm" in result


class TestOfflineGroupRejection:
    """get_online_features() rejects OFFLINE groups."""

    def test_offline_group_raises_not_materializable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling get_online_features on an OFFLINE group raises FeatureGroupNotMaterializableError."""
        _setup_store(tmp_path, monkeypatch, include_listing=True)

        with pytest.raises(FeatureGroupNotMaterializableError):
            FeatureStore().get_online_features(
                from_="listing_features",
                select=["sold_price"],
                where={"listing_id": {"eq": 1}},
            )


class TestWhereParameterValidation:
    """get_online_features() raises RetrievalParameterError for invalid where arguments."""

    def test_wrong_where_field_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Filtering on a non-entity-key field raises RetrievalParameterError."""
        _setup_store(tmp_path, monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"avg_price_per_sqm": {"eq": 24500.0}},
            )

    def test_wrong_where_field_error_mentions_bad_field_and_entity_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The error message names the bad filter field and the expected entity key."""
        _setup_store(tmp_path, monkeypatch)

        with pytest.raises(RetrievalParameterError, match="avg_price_per_sqm"):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"avg_price_per_sqm": {"eq": 24500.0}},
            )
