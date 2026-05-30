"""Integration tests for Feature 7: end-to-end local offline store ingestion."""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from kitefs.sdk.feature_store import FeatureStore
from kitefs.sdk.results import IngestResult
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

_UTC = datetime.UTC
_TS_FEB = datetime.datetime(2024, 2, 1, tzinfo=_UTC)
_TS_MAR = datetime.datetime(2024, 3, 1, tzinfo=_UTC)

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


def _setup_applied_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FeatureStore:
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    FeatureStore().apply()
    return FeatureStore()


class TestIngestDataFrame:
    """Full ingest flow from DataFrame to Parquet on disk."""

    def test_ingest_returns_ingest_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingesting a valid DataFrame returns an IngestResult."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        frame = town_market_frame(
            [
                {"town_id": i, "avg_price_per_sqm": float(20000 + i * 100), "event_timestamp": _TS_FEB}
                for i in range(1, 7)
            ]
        )

        result = store.ingest("town_market_features", frame)

        assert isinstance(result, IngestResult)
        assert result.accepted_rows == 6
        assert result.rejected_rows == 0
        assert len(result.written_files) == 1

    def test_ingest_creates_hive_partitioned_parquet(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parquet file is placed in year=2024/month=02 partition."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        frame = town_market_frame([{"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _TS_FEB}])

        result = store.ingest("town_market_features", frame)

        expected_dir = (
            tmp_path / "feature_store" / "data" / "offline_store" / "town_market_features" / "year=2024" / "month=02"
        )
        assert expected_dir.is_dir()
        assert len(list(expected_dir.glob("*.parquet"))) == 1
        assert len(result.written_files) == 1
        assert Path(result.written_files[0]).parent == expected_dir

    def test_ingest_parquet_readable_with_correct_columns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Written Parquet file is readable and contains declared columns."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        frame = town_market_frame([{"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _TS_FEB}])

        result = store.ingest("town_market_features", frame)

        table = pq.read_table(result.written_files[0])
        assert {"town_id", "event_timestamp", "avg_price_per_sqm"}.issubset(set(table.schema.names))

    def test_ingest_parquet_row_count(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Written Parquet file contains the expected number of rows."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        frame = town_market_frame(
            [
                {"town_id": i, "avg_price_per_sqm": float(20000 + i * 100), "event_timestamp": _TS_FEB}
                for i in range(1, 4)
            ]
        )

        result = store.ingest("town_market_features", frame)

        table = pq.read_table(result.written_files[0])
        assert len(table) == 3

    def test_ingest_multi_month_produces_two_partitions(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Rows in two different months produce two partition directories."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        frame = town_market_frame(
            [
                {"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _TS_FEB},
                {"town_id": 2, "avg_price_per_sqm": 25000.0, "event_timestamp": _TS_MAR},
            ]
        )

        result = store.ingest("town_market_features", frame)

        assert result.accepted_rows == 2
        assert len(result.written_files) == 2

        partition_dirs = {Path(p).parent.name for p in result.written_files}
        assert partition_dirs == {"month=02", "month=03"}

    def test_two_ingests_to_same_partition_appends(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Second ingest to the same month appends a new file, keeping the first."""
        store = _setup_applied_store(tmp_path, monkeypatch)
        frame = town_market_frame([{"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _TS_FEB}])

        result1 = store.ingest("town_market_features", frame)
        result2 = store.ingest("town_market_features", frame)

        assert result1.written_files[0] != result2.written_files[0]
        assert Path(result1.written_files[0]).exists()
        assert Path(result2.written_files[0]).exists()


class TestIngestCsvPath:
    """Ingest from a CSV file path."""

    def test_csv_ingest_returns_ingest_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingesting from a .csv file path returns IngestResult with accepted_rows > 0."""
        store = _setup_applied_store(tmp_path, monkeypatch)

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        csv_path = data_dir / "town_market_2024_02.csv"
        rows = [
            {"town_id": i, "avg_price_per_sqm": float(20000 + i * 100), "event_timestamp": "2024-02-01T00:00:00+00:00"}
            for i in range(1, 7)
        ]
        pd.DataFrame(rows).to_csv(csv_path, index=False)

        result = store.ingest("town_market_features", str(csv_path))

        assert isinstance(result, IngestResult)
        assert result.accepted_rows == 6
        assert len(result.written_files) == 1


class TestIngestParquetPath:
    """Ingest from a Parquet file path."""

    def test_parquet_ingest_returns_ingest_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingesting from a .parquet file path returns IngestResult with accepted_rows > 0."""
        store = _setup_applied_store(tmp_path, monkeypatch)

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        parquet_path = data_dir / "town_market_2024_02.parquet"
        rows = [
            {"town_id": i, "avg_price_per_sqm": float(20000 + i * 100), "event_timestamp": _TS_FEB} for i in range(1, 7)
        ]
        pd.DataFrame(rows).to_parquet(parquet_path, index=False)

        result = store.ingest("town_market_features", str(parquet_path))

        assert isinstance(result, IngestResult)
        assert result.accepted_rows == 6
        assert len(result.written_files) == 1

    def test_parquet_ingest_creates_hive_partition(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parquet source file ends up in the correct year=2024/month=02 partition."""
        store = _setup_applied_store(tmp_path, monkeypatch)

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        parquet_path = data_dir / "town_market_2024_02.parquet"
        pd.DataFrame([{"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _TS_FEB}]).to_parquet(
            parquet_path, index=False
        )

        result = store.ingest("town_market_features", str(parquet_path))

        expected_dir = (
            tmp_path / "feature_store" / "data" / "offline_store" / "town_market_features" / "year=2024" / "month=02"
        )
        assert expected_dir.is_dir()
        assert len(result.written_files) == 1
        assert Path(result.written_files[0]).parent == expected_dir
