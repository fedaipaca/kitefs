"""Tests for FeatureStore.ingest() — success paths, error paths, validation modes."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
from helpers import LISTING_DEF, TOWN_DEF, setup_project

from kitefs.exceptions import (
    DataValidationError,
    FeatureGroupNotFoundError,
    IngestionError,
    ProviderError,
    SchemaValidationError,
)
from kitefs.feature_store import FeatureStore, IngestResult

# ---------------------------------------------------------------------------
# Definition templates for validation mode tests
# ---------------------------------------------------------------------------

_FILTER_MODE_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, StorageTarget, ValidationMode,
)

filter_group = FeatureGroup(
    name="filter_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[
        Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().not_null()),
    ],
    ingestion_validation=ValidationMode.FILTER,
)
"""

_NONE_MODE_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, StorageTarget, ValidationMode,
)

none_group = FeatureGroup(
    name="none_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[
        Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)),
    ],
    ingestion_validation=ValidationMode.NONE,
)
"""

_ERROR_MODE_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, StorageTarget, ValidationMode,
)

error_group = FeatureGroup(
    name="error_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[
        Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)),
    ],
    ingestion_validation=ValidationMode.ERROR,
)
"""

# A simple definition for basic success tests (ERROR mode, no expectations).
_SIMPLE_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, StorageTarget,
)

simple_group = FeatureGroup(
    name="simple_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[Feature(name="value", dtype=FeatureType.FLOAT)],
)
"""


# ---------------------------------------------------------------------------
# DataFrame builders
# ---------------------------------------------------------------------------


def _make_simple_df(timestamps: list[str] | None = None) -> pd.DataFrame:
    """Build a minimal DataFrame matching the simple_group schema."""
    if timestamps is None:
        timestamps = ["2024-03-15", "2024-03-20"]
    n = len(timestamps)
    return pd.DataFrame(
        {
            "id": list(range(1, n + 1)),
            "ts": pd.to_datetime(timestamps),
            "value": [100.0 * i for i in range(1, n + 1)],
        }
    )


def _make_listing_df() -> pd.DataFrame:
    """Build a DataFrame matching the listing_features schema from the reference use case."""
    return pd.DataFrame(
        {
            "listing_id": [1, 2, 3],
            "event_timestamp": pd.to_datetime(["2024-03-15", "2024-04-10", "2024-04-20"]),
            "net_area": [80, 120, 95],
            "number_of_rooms": [3, 5, 4],
            "build_year": [2010, 1985, 2020],
            "sold_price": [500000.0, 750000.0, 620000.0],
            "town_id": [1, 2, 1],
        }
    )


# ---------------------------------------------------------------------------
# Helper: set up project with apply
# ---------------------------------------------------------------------------


def _setup_and_apply(
    tmp_path: Path,
    definitions: dict[str, str],
) -> FeatureStore:
    """Create a KiteFS project, write definitions, apply, and return the FeatureStore."""
    setup_project(tmp_path, definitions)
    fs = FeatureStore(project_root=tmp_path)
    fs.apply()
    return fs


# ---------------------------------------------------------------------------
# IngestResult dataclass
# ---------------------------------------------------------------------------


class TestIngestResult:
    """IngestResult is a frozen dataclass with the expected fields."""

    def test_importable_from_kitefs(self) -> None:
        """IngestResult is importable from the top-level kitefs package."""
        from kitefs import IngestResult as TopLevel

        assert TopLevel is IngestResult

    def test_fields_accessible(self) -> None:
        """IngestResult fields are accessible by name."""
        result = IngestResult(rows_written=10, partitions_affected=("year=2024/month=03",))
        assert result.rows_written == 10
        assert result.partitions_affected == ("year=2024/month=03",)

    def test_frozen(self) -> None:
        """IngestResult attributes cannot be reassigned."""
        result = IngestResult(rows_written=5, partitions_affected=())
        with pytest.raises(AttributeError):
            result.rows_written = 20  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


class TestIngestDataFrameSuccess:
    """FeatureStore.ingest() with valid DataFrame input."""

    def test_returns_ingest_result(self, tmp_path: Path) -> None:
        """Ingesting a valid DataFrame returns an IngestResult instance."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df()

        result = fs.ingest("simple_group", df)

        assert isinstance(result, IngestResult)

    def test_rows_written_matches_input(self, tmp_path: Path) -> None:
        """rows_written equals the number of input rows."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df()

        result = fs.ingest("simple_group", df)

        assert result.rows_written == len(df)

    def test_partitions_affected_correct(self, tmp_path: Path) -> None:
        """partitions_affected contains the expected partition paths."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df(["2024-03-15", "2024-03-20"])

        result = fs.ingest("simple_group", df)

        assert result.partitions_affected == ("year=2024/month=03",)

    def test_extra_columns_silently_dropped(self, tmp_path: Path) -> None:
        """Extra columns not in the definition are dropped before writing."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df()
        df["extra_col"] = "ignored"
        df["another_extra"] = 99

        result = fs.ingest("simple_group", df)

        assert result.rows_written == 2
        # Verify the written Parquet does not contain extra columns.
        storage = tmp_path / "feature_store" / "data" / "offline_store" / "simple_group"
        parquet_files = list(storage.rglob("*.parquet"))
        assert len(parquet_files) >= 1
        written_df = pq.read_table(parquet_files[0]).to_pandas()
        assert "extra_col" not in written_df.columns
        assert "another_extra" not in written_df.columns

    def test_empty_dataframe_returns_zero_rows(self, tmp_path: Path) -> None:
        """An empty DataFrame with correct columns returns IngestResult with 0 rows."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = pd.DataFrame(
            {
                "id": pd.Series(dtype="int64"),
                "ts": pd.Series(dtype="datetime64[us]"),
                "value": pd.Series(dtype="float64"),
            }
        )

        result = fs.ingest("simple_group", df)

        assert result.rows_written == 0
        assert result.partitions_affected == ()

    def test_data_spanning_multiple_partitions(self, tmp_path: Path) -> None:
        """Data with timestamps in different months produces multiple partitions."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df(["2024-03-15", "2024-04-10"])

        result = fs.ingest("simple_group", df)

        assert set(result.partitions_affected) == {
            "year=2024/month=03",
            "year=2024/month=04",
        }

    def test_data_spanning_multiple_years(self, tmp_path: Path) -> None:
        """Data with timestamps in different years produces year-separated partitions."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df(["2023-12-15", "2024-01-10"])

        result = fs.ingest("simple_group", df)

        assert set(result.partitions_affected) == {
            "year=2023/month=12",
            "year=2024/month=01",
        }

    def test_append_only_two_ingests_persist(self, tmp_path: Path) -> None:
        """Two sequential ingests both persist — no overwrite."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df1 = _make_simple_df(["2024-03-15"])
        df2 = _make_simple_df(["2024-03-20"])

        fs.ingest("simple_group", df1)
        fs.ingest("simple_group", df2)

        storage = tmp_path / "feature_store" / "data" / "offline_store" / "simple_group"
        parquet_files = list(storage.rglob("*.parquet"))
        assert len(parquet_files) == 2


class TestIngestFileSuccess:
    """FeatureStore.ingest() with file path input."""

    def test_csv_file_ingestion(self, tmp_path: Path) -> None:
        """Ingesting a CSV file path works."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df()
        csv_path = tmp_path / "data.csv"
        df.to_csv(csv_path, index=False)

        result = fs.ingest("simple_group", str(csv_path))

        assert result.rows_written == 2

    def test_parquet_file_ingestion(self, tmp_path: Path) -> None:
        """Ingesting a Parquet file path works."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df()
        parquet_path = tmp_path / "data.parquet"
        df.to_parquet(parquet_path, index=False)

        result = fs.ingest("simple_group", str(parquet_path))

        assert result.rows_written == 2


class TestIngestReferenceUseCase:
    """Ingest using the reference use case listing_features definition."""

    def test_listing_features_correct_partitions(self, tmp_path: Path) -> None:
        """Reference use case ingestion produces correct partition paths."""
        fs = _setup_and_apply(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        df = _make_listing_df()

        result = fs.ingest("listing_features", df)

        assert result.rows_written == 3
        assert set(result.partitions_affected) == {
            "year=2024/month=03",
            "year=2024/month=04",
        }


# ---------------------------------------------------------------------------
# Validation mode tests
# ---------------------------------------------------------------------------


class TestIngestValidationModes:
    """Validation mode behavior at the ingestion gate."""

    def test_none_mode_skips_data_validation(self, tmp_path: Path) -> None:
        """NONE mode accepts rows that would fail data expectations."""
        fs = _setup_and_apply(tmp_path, {"none.py": _NONE_MODE_DEF})
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-03-15", "2024-03-20"]),
                "value": [-1.0, -2.0],  # Violates gt(0) but NONE mode skips
            }
        )

        result = fs.ingest("none_group", df)

        assert result.rows_written == 2

    def test_filter_mode_excludes_failing_rows(self, tmp_path: Path) -> None:
        """FILTER mode excludes rows that fail expectations, keeps valid ones."""
        fs = _setup_and_apply(tmp_path, {"filter.py": _FILTER_MODE_DEF})
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "ts": pd.to_datetime(["2024-03-15", "2024-03-20", "2024-03-25"]),
                "value": [10.0, None, 30.0],  # Row 2 fails not_null
            }
        )

        result = fs.ingest("filter_group", df)

        assert result.rows_written == 2

    def test_filter_mode_all_filtered_returns_zero_rows(self, tmp_path: Path) -> None:
        """FILTER mode with all rows failing returns IngestResult with 0 rows."""
        fs = _setup_and_apply(tmp_path, {"filter.py": _FILTER_MODE_DEF})
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-03-15", "2024-03-20"]),
                "value": [None, None],  # All fail not_null
            }
        )

        result = fs.ingest("filter_group", df)

        assert result.rows_written == 0
        assert result.partitions_affected == ()

    def test_error_mode_invalid_data_raises_data_validation_error(self, tmp_path: Path) -> None:
        """ERROR mode with invalid data raises DataValidationError, no data written."""
        fs = _setup_and_apply(tmp_path, {"error.py": _ERROR_MODE_DEF})
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-03-15", "2024-03-20"]),
                "value": [-1.0, 5.0],  # Row 1 violates gt(0)
            }
        )

        with pytest.raises(DataValidationError):
            fs.ingest("error_group", df)

        # Verify no Parquet files were written.
        storage = tmp_path / "feature_store" / "data" / "offline_store" / "error_group"
        parquet_files = list(storage.rglob("*.parquet")) if storage.exists() else []
        assert len(parquet_files) == 0

    def test_schema_validation_runs_even_in_none_mode(self, tmp_path: Path) -> None:
        """Schema validation runs even when ingestion_validation is NONE."""
        fs = _setup_and_apply(tmp_path, {"none.py": _NONE_MODE_DEF})
        df = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-03-15"]),
                # "value" column is missing
            }
        )

        with pytest.raises(SchemaValidationError, match="Missing required column"):
            fs.ingest("none_group", df)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestIngestErrors:
    """FeatureStore.ingest() error cases."""

    def test_feature_group_not_found(self, tmp_path: Path) -> None:
        """Ingesting into a non-existent group raises FeatureGroupNotFoundError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df()

        with pytest.raises(FeatureGroupNotFoundError, match="nonexistent_group"):
            fs.ingest("nonexistent_group", df)

    def test_unsupported_type_raises_ingestion_error(self, tmp_path: Path) -> None:
        """Passing an unsupported type (e.g., int) raises IngestionError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})

        with pytest.raises(IngestionError, match="Unsupported"):
            fs.ingest("simple_group", 12345)  # type: ignore[arg-type]

    def test_unsupported_file_extension_raises_ingestion_error(self, tmp_path: Path) -> None:
        """Passing a file path with unsupported extension raises IngestionError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        json_path = tmp_path / "data.json"
        json_path.write_text("{}", encoding="utf-8")

        with pytest.raises(IngestionError) as exc_info:
            fs.ingest("simple_group", str(json_path))

        message = str(exc_info.value)
        assert ".csv" in message
        assert ".parquet" in message
        assert "Supported formats" in message

    def test_nonexistent_file_raises_ingestion_error(self, tmp_path: Path) -> None:
        """Passing a non-existent file path raises IngestionError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})

        with pytest.raises(IngestionError):
            fs.ingest("simple_group", str(tmp_path / "does_not_exist.csv"))

    def test_missing_columns_raises_schema_validation_error(self, tmp_path: Path) -> None:
        """A DataFrame missing a declared feature column raises SchemaValidationError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-03-15"]),
                # "value" is missing
            }
        )

        with pytest.raises(SchemaValidationError, match="Missing required column"):
            fs.ingest("simple_group", df)

    def test_null_entity_key_raises_schema_validation_error(self, tmp_path: Path) -> None:
        """Null entity key values raise SchemaValidationError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = pd.DataFrame(
            {
                "id": [1, None],
                "ts": pd.to_datetime(["2024-03-15", "2024-03-20"]),
                "value": [1.0, 2.0],
            }
        )

        with pytest.raises(SchemaValidationError, match=r"Entity key column.*null"):
            fs.ingest("simple_group", df)

    def test_null_event_timestamp_raises_schema_validation_error(self, tmp_path: Path) -> None:
        """Null event timestamp values raise SchemaValidationError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        ts = pd.Series(pd.to_datetime(["2024-03-15", "2024-03-20"]))
        ts.iloc[1] = None  # type: ignore[assignment]
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": ts,
                "value": [1.0, 2.0],
            }
        )

        with pytest.raises(SchemaValidationError, match=r"Event timestamp column.*null"):
            fs.ingest("simple_group", df)

    def test_malformed_csv_raises_ingestion_error(self, tmp_path: Path) -> None:
        """A malformed CSV file raises IngestionError, not a bare ParserError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("a,b\n1,2,3\n4,5,6,7", encoding="utf-8")

        with pytest.raises(IngestionError, match="Cannot read CSV file"):
            fs.ingest("simple_group", str(csv_path))

    def test_malformed_parquet_raises_ingestion_error(self, tmp_path: Path) -> None:
        """A file with random bytes and .parquet extension raises IngestionError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        parquet_path = tmp_path / "bad.parquet"
        parquet_path.write_bytes(b"\x00\x01\x02\x03 not a parquet file")

        with pytest.raises(IngestionError, match="Cannot read Parquet file"):
            fs.ingest("simple_group", str(parquet_path))

    def test_csv_ingestion_end_to_end_with_datetime(self, tmp_path: Path) -> None:
        """CSV file with datetime column is ingested and written to correct partitions."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df(["2024-06-15", "2024-07-20"])
        csv_path = tmp_path / "data.csv"
        df.to_csv(csv_path, index=False)

        result = fs.ingest("simple_group", str(csv_path))

        assert result.rows_written == 2
        assert set(result.partitions_affected) == {
            "year=2024/month=06",
            "year=2024/month=07",
        }

    def test_path_object_raises_ingestion_error(self, tmp_path: Path) -> None:
        """Passing a pathlib.Path object (not str) raises IngestionError."""
        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("id,ts,value\n1,2024-03-15,100.0", encoding="utf-8")

        with pytest.raises(IngestionError, match="Unsupported data type"):
            fs.ingest("simple_group", csv_path)  # type: ignore[arg-type]

    def test_provider_error_propagates_on_write_failure(self, tmp_path: Path) -> None:
        """ProviderError from the offline store write propagates through ingest()."""
        from unittest.mock import patch

        fs = _setup_and_apply(tmp_path, {"simple.py": _SIMPLE_DEF})
        df = _make_simple_df()

        with (
            patch.object(
                fs._offline_store_manager,
                "write",
                side_effect=ProviderError("Disk full"),
            ),
            pytest.raises(ProviderError, match="During ingest of feature group 'simple_group'"),
        ):
            fs.ingest("simple_group", df)
