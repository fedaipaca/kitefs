"""Integration tests for Feature 10: end-to-end local materialization."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kitefs.errors import FeatureGroupNotFoundError, FeatureGroupNotMaterializableError
from kitefs.sdk.feature_store import FeatureStore
from kitefs.sdk.results import MaterializeResult
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


def _ingest_market_rows(store: FeatureStore, n_months: int = 12, n_towns: int = 6) -> None:
    """Ingest n_months x n_towns rows into town_market_features."""
    for month in range(1, n_months + 1):
        rows = [
            {
                "town_id": town_id,
                "avg_price_per_sqm": float(20000 + town_id * 100 + month),
                "event_timestamp": _ts(f"2024-{month:02d}-01T00:00:00"),
            }
            for town_id in range(1, n_towns + 1)
        ]
        store.ingest("town_market_features", town_market_frame(rows))


def _read_sqlite_rows(tmp_path: Path, table: str) -> list[dict]:
    """Read all rows from a SQLite table as a list of dicts."""
    db_path = tmp_path / "feature_store" / "data" / "online_store" / "online.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
    return [dict(r) for r in rows]


class TestMaterializeNamedGroup:
    """store.materialize('town_market_features') populates the online store."""

    def test_returns_materialize_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """materialize() returns a MaterializeResult."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_market_rows(store)
        result = store.materialize("town_market_features")
        assert isinstance(result, MaterializeResult)

    def test_succeeded_contains_group_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """result.succeeded contains the materialized group name."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_market_rows(store)
        result = store.materialize("town_market_features")
        assert "town_market_features" in result.succeeded
        assert result.skipped == []
        assert result.failed == []

    def test_sqlite_has_one_row_per_town(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SQLite table contains exactly one row per entity key (6 towns)."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_market_rows(store, n_months=12, n_towns=6)
        store.materialize("town_market_features")
        rows = _read_sqlite_rows(tmp_path, "town_market_features")
        assert len(rows) == 6

    def test_sqlite_row_has_latest_timestamp(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each row in SQLite has the December 2024 (latest) event_timestamp."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_market_rows(store, n_months=12, n_towns=6)
        store.materialize("town_market_features")
        rows = _read_sqlite_rows(tmp_path, "town_market_features")
        for row in rows:
            assert row["event_timestamp"].startswith("2024-12")

    def test_registry_last_materialized_at_is_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """last_materialized_at is updated in the registry after materialization."""
        store = _setup_store(tmp_path, monkeypatch)
        _ingest_market_rows(store)
        store.materialize("town_market_features")
        desc = store.describe_feature_group("town_market_features")
        assert desc.last_materialized_at is not None


class TestMaterializeAllGroups:
    """store.materialize() with no argument materializes all online-capable groups."""

    def test_all_online_groups_materialized(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """All OFFLINE_AND_ONLINE groups appear in result.succeeded."""
        store = _setup_store(tmp_path, monkeypatch, include_listing=False)
        _ingest_market_rows(store)
        result = store.materialize()
        assert "town_market_features" in result.succeeded

    def test_offline_only_group_excluded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """OFFLINE-only groups do not appear in result at all."""
        store = _setup_store(tmp_path, monkeypatch, include_listing=True)
        _ingest_market_rows(store)
        result = store.materialize()
        all_names = result.succeeded + [s.name for s in result.skipped] + [f.name for f in result.failed]
        assert "listing_features" not in all_names

    def test_empty_result_when_no_online_groups(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """All-groups run with only OFFLINE groups returns an empty result."""
        _setup_store(tmp_path, monkeypatch, include_listing=True)
        # Remove town_market definition so only listing_features is present.
        (tmp_path / "feature_store" / "definitions" / "town_market_features.py").unlink()
        FeatureStore().apply()
        result = FeatureStore().materialize()
        assert result.succeeded == []
        assert result.skipped == []
        assert result.failed == []


class TestMaterializeErrors:
    """materialize() raises for unknown and offline-only named groups."""

    def test_unknown_group_raises_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Named group not in registry raises FeatureGroupNotFoundError."""
        store = _setup_store(tmp_path, monkeypatch)
        with pytest.raises(FeatureGroupNotFoundError, match="neighborhood_features"):
            store.materialize("neighborhood_features")

    def test_offline_only_group_raises_not_materializable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Named OFFLINE group raises FeatureGroupNotMaterializableError."""
        store = _setup_store(tmp_path, monkeypatch, include_listing=True)
        with pytest.raises(FeatureGroupNotMaterializableError, match="listing_features"):
            store.materialize("listing_features")


class TestMaterializeSkipped:
    """Groups with no offline data produce a SkippedGroup in the result."""

    def test_skipped_when_no_offline_data(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A group with zero offline rows produces a SkippedGroup."""
        store = _setup_store(tmp_path, monkeypatch)
        result = store.materialize("town_market_features")
        assert len(result.skipped) == 1
        assert result.skipped[0].name == "town_market_features"
        assert result.skipped[0].reason == "no offline data"
        assert result.succeeded == []
        assert result.failed == []

    def test_skipped_preserves_existing_online_state(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Skipping a group does not disturb an already-materialized table."""
        store = _setup_store(tmp_path, monkeypatch)
        # First ingest and materialize normally.
        _ingest_market_rows(store, n_months=1, n_towns=3)
        store.materialize("town_market_features")
        rows_before = _read_sqlite_rows(tmp_path, "town_market_features")

        # Delete offline data artificially to force a skip on the next call,
        # by re-applying with a fresh FeatureStore pointing to same registry.
        # (We just call materialize again after the offline dir is cleared.)
        import shutil

        shutil.rmtree(tmp_path / "feature_store" / "data" / "offline_store" / "town_market_features")
        result = store.materialize("town_market_features")

        assert result.skipped[0].name == "town_market_features"
        rows_after = _read_sqlite_rows(tmp_path, "town_market_features")
        assert rows_after == rows_before
