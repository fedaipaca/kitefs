"""Unit tests for FeatureStore.ingest() orchestration (error paths and unit behaviour)."""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from kitefs.errors import FeatureGroupNotFoundError, IngestionShapeError
from kitefs.sdk.feature_store import FeatureStore
from kitefs.sdk.results import IngestResult
from tests.helpers.dataframes import town_market_frame
from tests.helpers.tmp_store import make_initialized_project

_UTC = datetime.UTC
_TS_FEB = datetime.datetime(2024, 2, 1, tzinfo=_UTC)

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

_FILTER_TOWN_MARKET_SRC = _TOWN_MARKET_SRC.replace(
    "ingestion_validation=ValidationMode.ERROR",
    "ingestion_validation=ValidationMode.FILTER",
)


def _setup_project(tmp_path: Path, src: str = _TOWN_MARKET_SRC) -> Path:
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(src, encoding="utf-8")
    return tmp_path


def _valid_frame() -> pd.DataFrame:
    return town_market_frame([{"town_id": 1, "avg_price_per_sqm": 24500.0, "event_timestamp": _TS_FEB}])


class TestIngestErrors:
    """FeatureStore.ingest() raises appropriate errors for invalid inputs."""

    def test_unknown_group_raises_feature_group_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ingesting into an unregistered group raises FeatureGroupNotFoundError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        with pytest.raises(FeatureGroupNotFoundError):
            FeatureStore().ingest("nonexistent_group", _valid_frame())

    def test_unsupported_extension_raises_ingestion_shape_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Passing a .xlsx path raises IngestionShapeError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        with pytest.raises(IngestionShapeError):
            FeatureStore().ingest("town_market_features", "data/file.xlsx")

    def test_unsupported_extension_message_contains_csv_and_parquet(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """.xlsx error message names .csv and .parquet as the supported formats."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        with pytest.raises(IngestionShapeError) as exc_info:
            FeatureStore().ingest("town_market_features", "data/file.xlsx")

        msg = str(exc_info.value)
        assert ".csv" in msg
        assert ".parquet" in msg

    def test_missing_required_column_raises_ingestion_shape_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DataFrame missing a declared column raises IngestionShapeError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        frame = pd.DataFrame({"town_id": [1], "event_timestamp": [_TS_FEB]})

        with pytest.raises(IngestionShapeError):
            FeatureStore().ingest("town_market_features", frame)


class TestIngestFilterMode:
    """FeatureStore.ingest() in FILTER mode returns IngestResult without writing when all rows fail."""

    def test_all_rejected_returns_empty_written_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FILTER mode with all rows invalid returns IngestResult with accepted_rows=0 and no files."""
        _setup_project(tmp_path, _FILTER_TOWN_MARKET_SRC)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        frame = town_market_frame(
            [
                {"town_id": 1, "avg_price_per_sqm": -10.0, "event_timestamp": _TS_FEB},
                {"town_id": 2, "avg_price_per_sqm": -20.0, "event_timestamp": _TS_FEB},
            ]
        )

        result = FeatureStore().ingest("town_market_features", frame)

        assert isinstance(result, IngestResult)
        assert result.accepted_rows == 0
        assert result.written_files == []
        assert result.rejected_rows == 2

    def test_all_rejected_validation_report_is_returned(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FILTER mode with all rows invalid still returns a ValidationReport."""
        _setup_project(tmp_path, _FILTER_TOWN_MARKET_SRC)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        frame = town_market_frame([{"town_id": 1, "avg_price_per_sqm": -5.0, "event_timestamp": _TS_FEB}])

        result = FeatureStore().ingest("town_market_features", frame)

        assert result.validation_report is not None


class TestIngestHappyPath:
    """FeatureStore.ingest() returns correct IngestResult on success."""

    def test_returns_ingest_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy-path ingest returns an IngestResult with correct feature_group."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        result = FeatureStore().ingest("town_market_features", _valid_frame())

        assert isinstance(result, IngestResult)
        assert result.feature_group == "town_market_features"

    def test_accepted_rows_count(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """accepted_rows reflects the number of rows written."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        frame = town_market_frame(
            [{"town_id": i, "avg_price_per_sqm": float(20000 + i), "event_timestamp": _TS_FEB} for i in range(1, 4)]
        )
        result = FeatureStore().ingest("town_market_features", frame)

        assert result.accepted_rows == 3
        assert result.rejected_rows == 0

    def test_written_files_not_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """written_files is non-empty on a successful ingest."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        result = FeatureStore().ingest("town_market_features", _valid_frame())

        assert len(result.written_files) >= 1

    def test_written_file_exists_on_disk(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each path in written_files refers to an existing Parquet file."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        result = FeatureStore().ingest("town_market_features", _valid_frame())

        for path in result.written_files:
            assert Path(path).exists(), f"Written file does not exist: {path}"
