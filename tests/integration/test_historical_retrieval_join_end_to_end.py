"""Integration tests for Feature 9: point-in-time historical retrieval with joins."""

from __future__ import annotations

import datetime
import time
from pathlib import Path

import pandas as pd
import pytest

from kitefs.errors import ValidationError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.dataframes import listing_features_frame, town_market_frame
from tests.helpers.tmp_store import make_initialized_project

_UTC = datetime.UTC

_TOWN_MARKET_SRC_TEMPLATE = """\
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
        Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT, expect=Expect().gt(0)),
    ],
    ingestion_validation={ingestion_validation},
    offline_retrieval_validation={retrieval_validation},
    metadata=Metadata(description="Town market", owner="team", tags={{}}),
)
"""

_LISTING_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    JoinKey, Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="net_area", dtype=FeatureType.INTEGER),
        Feature(name="sold_price", dtype=FeatureType.FLOAT),
    ],
    join_keys=[
        JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features"),
    ],
    ingestion_validation=ValidationMode.NONE,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(description="Listing features", owner="team", tags={}),
)
"""


def _setup_applied_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    market_retrieval_validation: str = "ValidationMode.NONE",
    market_ingestion_validation: str = "ValidationMode.NONE",
) -> FeatureStore:
    """Create a project, write definitions, apply, and return the SDK instance."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    town_market_src = _TOWN_MARKET_SRC_TEMPLATE.format(
        retrieval_validation=market_retrieval_validation,
        ingestion_validation=market_ingestion_validation,
    )
    (defs_dir / "town_market_features.py").write_text(town_market_src, encoding="utf-8")
    (defs_dir / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    store = FeatureStore()
    store.apply()
    return store


def _ingest_common_market_rows(store: FeatureStore) -> None:
    """Ingest market snapshots for towns 1 and 3."""
    market_rows = [
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC), "avg_price_per_sqm": 20000.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 3, 1, tzinfo=_UTC), "avg_price_per_sqm": 23000.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 4, 1, tzinfo=_UTC), "avg_price_per_sqm": 26000.0},
        {"town_id": 1, "event_timestamp": datetime.datetime(2024, 5, 1, tzinfo=_UTC), "avg_price_per_sqm": 30000.0},
        {"town_id": 3, "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC), "avg_price_per_sqm": 18000.0},
    ]
    store.ingest("town_market_features", town_market_frame(market_rows))


class TestHistoricalRetrievalWithJoin:
    """Joined historical retrieval respects point-in-time semantics."""

    def test_latest_eligible_market_row_used_for_listing_1002(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A listing joins to the latest market snapshot at or before sold_at."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        _ingest_common_market_rows(store)

        listing_rows = [
            {
                "listing_id": 1002,
                "sold_at": datetime.datetime(2024, 4, 5, 14, 0, 0, tzinfo=_UTC),
                "town_id": 1,
                "net_area": 90,
                "sold_price": 410000.0,
            }
        ]
        store.ingest("listing_features", listing_features_frame(listing_rows))

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select={
                "listing_features": ["net_area", "sold_price"],
                "town_market_features": ["avg_price_per_sqm"],
            },
            where={
                "sold_at": {
                    "gte": datetime.datetime(2024, 3, 1, tzinfo=_UTC),
                    "lte": datetime.datetime(2024, 5, 31, 23, 59, 59, tzinfo=_UTC),
                }
            },
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.loc[0, "town_market_features_avg_price_per_sqm"] == 26000.0
        assert result.loc[0, "town_market_features_event_timestamp"] == datetime.datetime(2024, 4, 1, 0, 0, 0)

    def test_base_row_without_eligible_join_keeps_null_columns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A base row sold before the first snapshot keeps null joined values."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        _ingest_common_market_rows(store)

        listing_rows = [
            {
                "listing_id": 1010,
                "sold_at": datetime.datetime(2024, 1, 20, 17, 0, 0, tzinfo=_UTC),
                "town_id": 3,
                "net_area": 75,
                "sold_price": 280000.0,
            }
        ]
        store.ingest("listing_features", listing_features_frame(listing_rows))

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select={
                "listing_features": ["net_area"],
                "town_market_features": ["avg_price_per_sqm"],
            },
        )

        assert len(result) == 1
        assert result.loc[0, "listing_id"] == 1010
        assert pd.isna(result.loc[0, "town_market_features_avg_price_per_sqm"])

    def test_joined_side_ignores_base_where_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Joined data older than base where range remains eligible for point-in-time joins."""
        store = _setup_applied_store(tmp_path, monkeypatch)

        market_rows = [
            {"town_id": 1, "event_timestamp": datetime.datetime(2024, 2, 1, tzinfo=_UTC), "avg_price_per_sqm": 21000.0},
            {"town_id": 1, "event_timestamp": datetime.datetime(2024, 5, 1, tzinfo=_UTC), "avg_price_per_sqm": 29000.0},
        ]
        store.ingest("town_market_features", town_market_frame(market_rows))

        listing_rows = [
            {
                "listing_id": 2001,
                "sold_at": datetime.datetime(2024, 4, 5, 9, 0, 0, tzinfo=_UTC),
                "town_id": 1,
                "net_area": 85,
                "sold_price": 350000.0,
            }
        ]
        store.ingest("listing_features", listing_features_frame(listing_rows))

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select={
                "listing_features": ["net_area"],
                "town_market_features": ["avg_price_per_sqm"],
            },
            where={
                "sold_at": {
                    "gte": datetime.datetime(2024, 4, 1, tzinfo=_UTC),
                    "lte": datetime.datetime(2024, 4, 30, 23, 59, 59, tzinfo=_UTC),
                }
            },
        )

        assert len(result) == 1
        assert result.loc[0, "town_market_features_avg_price_per_sqm"] == 21000.0

    def test_joined_retrieval_validation_runs_independently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid joined rows raise ValidationError under joined ERROR retrieval mode."""
        store = _setup_applied_store(
            tmp_path,
            monkeypatch,
            market_retrieval_validation="ValidationMode.ERROR",
            market_ingestion_validation="ValidationMode.NONE",
        )

        market_rows = [
            {"town_id": 1, "event_timestamp": datetime.datetime(2024, 4, 1, tzinfo=_UTC), "avg_price_per_sqm": -1.0},
        ]
        store.ingest("town_market_features", town_market_frame(market_rows))

        listing_rows = [
            {
                "listing_id": 3001,
                "sold_at": datetime.datetime(2024, 4, 5, 9, 0, 0, tzinfo=_UTC),
                "town_id": 1,
                "net_area": 88,
                "sold_price": 360000.0,
            }
        ]
        store.ingest("listing_features", listing_features_frame(listing_rows))

        with pytest.raises(ValidationError):
            FeatureStore().get_historical_features(
                from_="listing_features",
                join=["town_market_features"],
                select={
                    "listing_features": ["net_area"],
                    "town_market_features": ["avg_price_per_sqm"],
                },
            )

    def test_equal_timestamp_tie_broken_by_ingestion_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Later-ingested row wins when two joined rows tie on event_timestamp."""
        store = _setup_applied_store(tmp_path, monkeypatch)

        store.ingest(
            "town_market_features",
            town_market_frame(
                [
                    {
                        "town_id": 1,
                        "event_timestamp": datetime.datetime(2024, 4, 1, tzinfo=_UTC),
                        "avg_price_per_sqm": 20000.0,
                    }
                ]
            ),
        )
        # Ensure distinct file modification time for the second ingest so that
        # the local store's (st_mtime_ns, path) sort exposes ingestion order.
        time.sleep(0.01)
        store.ingest(
            "town_market_features",
            town_market_frame(
                [
                    {
                        "town_id": 1,
                        "event_timestamp": datetime.datetime(2024, 4, 1, tzinfo=_UTC),
                        "avg_price_per_sqm": 25000.0,
                    }
                ]
            ),
        )

        store.ingest(
            "listing_features",
            listing_features_frame(
                [
                    {
                        "listing_id": 4001,
                        "sold_at": datetime.datetime(2024, 4, 5, tzinfo=_UTC),
                        "town_id": 1,
                        "net_area": 80,
                        "sold_price": 300000.0,
                    }
                ]
            ),
        )

        result = FeatureStore().get_historical_features(
            from_="listing_features",
            join=["town_market_features"],
            select={
                "listing_features": ["net_area"],
                "town_market_features": ["avg_price_per_sqm"],
            },
        )

        assert len(result) == 1
        assert result.loc[0, "town_market_features_avg_price_per_sqm"] == 25000.0
