"""Integration tests for Feature 8: end-to-end local offline store historical retrieval."""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from kitefs.errors import ValidationError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.dataframes import listing_features_frame
from tests.helpers.tmp_store import make_initialized_project

_UTC = datetime.UTC
_TS_FEB = datetime.datetime(2024, 2, 15, tzinfo=_UTC)
_TS_MAR = datetime.datetime(2024, 3, 15, tzinfo=_UTC)
_TS_APR = datetime.datetime(2024, 4, 15, tzinfo=_UTC)

_TOWN_MARKET_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[
        Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT),
    ],
    ingestion_validation=ValidationMode.NONE,
    metadata=Metadata(description="Town market", owner="team", tags={}),
)
"""

_LISTING_SRC_TEMPLATE = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup, FeatureType,
    JoinKey, Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="build_year", dtype=FeatureType.INTEGER, expect=Expect().not_null().gte(1900).lte(2030)),
        Feature(name="net_area", dtype=FeatureType.INTEGER, expect=Expect().not_null().gt(0)),
        Feature(name="number_of_rooms", dtype=FeatureType.INTEGER, expect=Expect().not_null().gt(0)),
        Feature(name="sold_price", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)),
    ],
    join_keys=[
        JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features"),
    ],
    ingestion_validation={ingestion_validation},
    offline_retrieval_validation={retrieval_validation},
    metadata=Metadata(description="Listing features", owner="team", tags={{}}),
)
"""


def _sample_listing_rows() -> list[dict]:
    return [
        {
            "listing_id": 1,
            "sold_at": _TS_FEB,
            "town_id": 1,
            "net_area": 80,
            "number_of_rooms": 3,
            "build_year": 2000,
            "sold_price": 250000.0,
        },
        {
            "listing_id": 2,
            "sold_at": _TS_MAR,
            "town_id": 1,
            "net_area": 120,
            "number_of_rooms": 4,
            "build_year": 2010,
            "sold_price": 400000.0,
        },
        {
            "listing_id": 3,
            "sold_at": _TS_APR,
            "town_id": 2,
            "net_area": 60,
            "number_of_rooms": 2,
            "build_year": 1995,
            "sold_price": 180000.0,
        },
    ]


def _setup_applied_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retrieval_validation: str = "ValidationMode.NONE",
    ingestion_validation: str = "ValidationMode.ERROR",
) -> FeatureStore:
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    listing_src = _LISTING_SRC_TEMPLATE.format(
        retrieval_validation=retrieval_validation,
        ingestion_validation=ingestion_validation,
    )
    (defs_dir / "listing_features.py").write_text(listing_src, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    FeatureStore().apply()
    return FeatureStore()


def _ingest_listing_rows(store: FeatureStore) -> None:
    frame = listing_features_frame(_sample_listing_rows())
    store.ingest("listing_features", frame)


class TestGetHistoricalFeaturesBasic:
    """get_historical_features() returns correct rows and columns."""

    def test_returns_structural_and_selected_columns(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Result contains entity key, event timestamp, join keys, and selected features."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        _ingest_listing_rows(store)

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["listing_id", "sold_at", "town_id", "net_area", "sold_price"]

    def test_returns_all_rows_without_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without a filter, all ingested rows are returned."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        _ingest_listing_rows(store)

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area"],
        )

        assert len(result) == 3

    def test_wildcard_select_returns_all_features(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """select=['*'] returns structural columns plus all declared feature columns."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        _ingest_listing_rows(store)

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["*"],
        )

        assert isinstance(result, pd.DataFrame)
        expected = {"listing_id", "sold_at", "town_id", "net_area", "number_of_rooms", "build_year", "sold_price"}
        assert set(result.columns) == expected

    def test_wildcard_returns_all_rows(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Wildcard select returns all ingested rows."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        _ingest_listing_rows(store)

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["*"],
        )

        assert len(result) == 3

    def test_empty_group_returns_zero_rows_with_columns(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reading a group with no ingested data returns an empty DataFrame with the right columns."""
        _setup_applied_store(tmp_path, monkeypatch)
        # No ingest

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        assert list(result.columns) == ["listing_id", "sold_at", "town_id", "net_area", "sold_price"]


class TestGetHistoricalFeaturesFilter:
    """get_historical_features() applies where= timestamp filters correctly."""

    def test_gte_lte_filter_returns_matching_month(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A gte/lte filter bounded to April 2024 returns only April rows."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        _ingest_listing_rows(store)

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area"],
            where={
                "sold_at": {
                    "gte": datetime.datetime(2024, 4, 1, tzinfo=_UTC),
                    "lte": datetime.datetime(2024, 4, 30, 23, 59, 59, tzinfo=_UTC),
                }
            },
        )

        assert len(result) == 1
        assert result["listing_id"].iloc[0] == 3

    def test_future_filter_returns_empty_dataframe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A filter range with no matching rows returns an empty DataFrame."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        _ingest_listing_rows(store)

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            select=["net_area", "sold_price"],
            where={
                "sold_at": {
                    "gte": datetime.datetime(2030, 12, 1, tzinfo=_UTC),
                    "lte": datetime.datetime(2030, 12, 31, 23, 59, 59, tzinfo=_UTC),
                }
            },
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        assert list(result.columns) == ["listing_id", "sold_at", "town_id", "net_area", "sold_price"]


class TestGetHistoricalFeaturesValidation:
    """get_historical_features() applies offline_retrieval_validation correctly."""

    def test_validation_error_mode_raises_on_invalid_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ERROR retrieval mode raises ValidationError when stored rows violate expectations."""
        # Use NONE ingestion validation so the bad row can be stored,
        # and ERROR retrieval validation so it fails when read back.
        store = _setup_applied_store(
            tmp_path,
            monkeypatch,
            retrieval_validation="ValidationMode.ERROR",
            ingestion_validation="ValidationMode.NONE",
        )
        bad_rows = [
            {
                "listing_id": 1,
                "sold_at": _TS_FEB,
                "town_id": 1,
                "net_area": 80,
                "number_of_rooms": 3,
                "build_year": 2000,
                "sold_price": 0.0,  # violates Expect().not_null().gt(0)
            }
        ]
        store.ingest("listing_features", listing_features_frame(bad_rows))

        with pytest.raises(ValidationError):
            FeatureStore().get_historical_features(
                from_="listing_features",
                select=["net_area", "sold_price"],
            )
