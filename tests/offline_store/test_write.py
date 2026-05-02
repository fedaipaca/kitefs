"""Tests for OfflineStoreManager.write() — partition derivation, file naming, delegation."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
from helpers import make_local_config

from kitefs.exceptions import IngestionError
from kitefs.offline_store import OfflineStoreManager
from kitefs.providers.local import LocalProvider

_FILE_NAME_PATTERN = re.compile(r"^[a-z]+_\d{8}T\d{6}_[0-9a-f]{8}\.parquet$")


def _make_manager(tmp_path: Path) -> tuple[OfflineStoreManager, LocalProvider, Path]:
    """Create an OfflineStoreManager backed by a LocalProvider in tmp_path."""
    config = make_local_config(tmp_path)
    config.storage_root.mkdir(parents=True, exist_ok=True)
    provider = LocalProvider(config)
    manager = OfflineStoreManager(provider)
    return manager, provider, config.storage_root


def _make_df(timestamps: list[str]) -> pd.DataFrame:
    """Build a minimal DataFrame with an entity key, event timestamp, and a feature."""
    return pd.DataFrame(
        {
            "id": list(range(1, len(timestamps) + 1)),
            "event_timestamp": pd.to_datetime(timestamps),
            "value": [100.0 * i for i in range(1, len(timestamps) + 1)],
        }
    )


class TestWriteSinglePartition:
    """Write records that all fall into a single year/month partition."""

    def test_returns_correct_rows_written(self, tmp_path: Path) -> None:
        """WriteResult.rows_written matches the input DataFrame length."""
        manager, _, _ = _make_manager(tmp_path)
        df = _make_df(["2024-03-15", "2024-03-20"])

        result = manager.write("test_group", df, "event_timestamp")

        assert result.rows_written == 2

    def test_returns_single_partition(self, tmp_path: Path) -> None:
        """WriteResult.partitions_affected has exactly one entry for single-month data."""
        manager, _, _ = _make_manager(tmp_path)
        df = _make_df(["2024-03-15", "2024-03-20"])

        result = manager.write("test_group", df, "event_timestamp")

        assert result.partitions_affected == ("year=2024/month=03",)

    def test_parquet_file_created_in_correct_directory(self, tmp_path: Path) -> None:
        """A Parquet file exists under the expected partition directory."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = _make_df(["2024-03-15"])

        manager.write("my_group", df, "event_timestamp")

        partition_dir = storage_root / "data" / "offline_store" / "my_group" / "year=2024" / "month=03"
        parquet_files = list(partition_dir.glob("*.parquet"))
        assert len(parquet_files) == 1

    def test_file_name_follows_naming_pattern(self, tmp_path: Path) -> None:
        """Written file name matches {source}_{YYYYMMDDTHHMMSS}_{short_id}.parquet."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = _make_df(["2024-03-15"])

        manager.write("test_group", df, "event_timestamp")

        partition_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=03"
        parquet_file = next(partition_dir.glob("*.parquet"))
        assert _FILE_NAME_PATTERN.match(parquet_file.name)
        assert parquet_file.name.startswith("ing_")

    def test_parquet_contains_original_columns_only(self, tmp_path: Path) -> None:
        """Written Parquet does not contain derived partition columns."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = _make_df(["2024-03-15"])

        manager.write("test_group", df, "event_timestamp")

        partition_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=03"
        parquet_file = next(partition_dir.glob("*.parquet"))
        # Use ParquetFile to avoid Hive-partition column inference from directory names.
        table = pq.ParquetFile(parquet_file).read()
        column_names = set(table.column_names)
        assert "id" in column_names
        assert "event_timestamp" in column_names
        assert "value" in column_names
        # Partition columns must NOT be in the Parquet file.
        assert "year" not in column_names
        assert "month" not in column_names

    def test_parquet_data_matches_input(self, tmp_path: Path) -> None:
        """Parquet file contents match the input DataFrame."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = _make_df(["2024-03-15", "2024-03-20"])

        manager.write("test_group", df, "event_timestamp")

        partition_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=03"
        read_df = pq.read_table(next(partition_dir.glob("*.parquet"))).to_pandas()
        assert len(read_df) == 2
        assert list(read_df["id"]) == [1, 2]


class TestWriteMultiplePartitions:
    """Write records spanning multiple year/month partitions."""

    def test_records_split_across_partitions(self, tmp_path: Path) -> None:
        """Records with different months go to different partition directories."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = _make_df(["2024-03-15", "2024-04-10", "2024-04-20"])

        result = manager.write("test_group", df, "event_timestamp")

        assert result.rows_written == 3
        assert set(result.partitions_affected) == {"year=2024/month=03", "year=2024/month=04"}

        mar_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=03"
        apr_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=04"
        assert len(list(mar_dir.glob("*.parquet"))) == 1
        assert len(list(apr_dir.glob("*.parquet"))) == 1

    def test_partitions_affected_sorted(self, tmp_path: Path) -> None:
        """partitions_affected is sorted lexicographically."""
        manager, _, _ = _make_manager(tmp_path)
        df = _make_df(["2024-12-01", "2024-01-15", "2024-06-10"])

        result = manager.write("test_group", df, "event_timestamp")

        assert result.partitions_affected == (
            "year=2024/month=01",
            "year=2024/month=06",
            "year=2024/month=12",
        )

    def test_records_spanning_years(self, tmp_path: Path) -> None:
        """Records from different years go to year-separated partitions."""
        manager, _, _ = _make_manager(tmp_path)
        df = _make_df(["2023-12-15", "2024-01-10"])

        result = manager.write("test_group", df, "event_timestamp")

        assert set(result.partitions_affected) == {"year=2023/month=12", "year=2024/month=01"}


class TestWriteCustomSourcePrefix:
    """Write with a non-default source_prefix."""

    def test_mock_prefix_in_file_name(self, tmp_path: Path) -> None:
        """source_prefix='mock' produces file names starting with 'mock_'."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = _make_df(["2024-03-15"])

        manager.write("test_group", df, "event_timestamp", source_prefix="mock")

        partition_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=03"
        parquet_file = next(partition_dir.glob("*.parquet"))
        assert parquet_file.name.startswith("mock_")


class TestWriteAppendOnly:
    """Append-only semantics — second write does not overwrite the first."""

    def test_two_writes_produce_two_files(self, tmp_path: Path) -> None:
        """Two writes to the same partition create two distinct Parquet files."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = _make_df(["2024-03-15"])

        manager.write("test_group", df, "event_timestamp")
        manager.write("test_group", df, "event_timestamp")

        partition_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=03"
        parquet_files = list(partition_dir.glob("*.parquet"))
        assert len(parquet_files) == 2

    def test_both_files_contain_data(self, tmp_path: Path) -> None:
        """Both files written by separate ingestions are independently readable."""
        manager, _, storage_root = _make_manager(tmp_path)
        df1 = _make_df(["2024-03-15"])
        df2 = _make_df(["2024-03-20"])

        manager.write("test_group", df1, "event_timestamp")
        manager.write("test_group", df2, "event_timestamp")

        partition_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=03"
        total_rows = 0
        for pf in partition_dir.glob("*.parquet"):
            total_rows += len(pq.read_table(pf).to_pandas())
        assert total_rows == 2


class TestWriteEmptyDataFrame:
    """Writing an empty DataFrame returns zero-count result without I/O."""

    def test_empty_df_returns_zero_result(self, tmp_path: Path) -> None:
        """Empty DataFrame produces WriteResult(rows_written=0, partitions_affected=())."""
        manager, _, _ = _make_manager(tmp_path)
        df = pd.DataFrame({"id": [], "event_timestamp": [], "value": []})

        result = manager.write("test_group", df, "event_timestamp")

        assert result.rows_written == 0
        assert result.partitions_affected == ()


class TestWriteNullTimestamp:
    """Null event timestamps raise IngestionError."""

    def test_null_timestamp_raises_ingestion_error(self, tmp_path: Path) -> None:
        """A null in the event timestamp column raises IngestionError."""
        manager, _, _ = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "event_timestamp": [datetime(2024, 3, 15), None],
                "value": [100.0, 200.0],
            }
        )

        with pytest.raises(IngestionError, match="null"):
            manager.write("test_group", df, "event_timestamp")

    def test_null_timestamp_reports_count(self, tmp_path: Path) -> None:
        """IngestionError message includes the number of null records."""
        manager, _, _ = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "event_timestamp": [None, None, datetime(2024, 3, 15)],
                "value": [100.0, 200.0, 300.0],
            }
        )

        with pytest.raises(IngestionError, match="2 record"):
            manager.write("test_group", df, "event_timestamp")

    def test_no_parquet_written_on_null_error(self, tmp_path: Path) -> None:
        """No files are written when null timestamps are detected."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "id": [1],
                "event_timestamp": [None],
                "value": [100.0],
            }
        )

        with pytest.raises(IngestionError):
            manager.write("test_group", df, "event_timestamp")

        group_dir = storage_root / "data" / "offline_store" / "test_group"
        assert not group_dir.exists()


class TestWriteUniqueFileNames:
    """Each write() call generates a unique file name."""

    def test_two_writes_produce_different_file_names(self, tmp_path: Path) -> None:
        """Two write() calls to the same partition produce files with different names."""
        manager, _, storage_root = _make_manager(tmp_path)
        df = _make_df(["2024-03-15"])

        manager.write("test_group", df, "event_timestamp")
        manager.write("test_group", df, "event_timestamp")

        partition_dir = storage_root / "data" / "offline_store" / "test_group" / "year=2024" / "month=03"
        names = sorted(p.name for p in partition_dir.glob("*.parquet"))
        assert len(names) == 2
        assert names[0] != names[1]


class TestWriteProviderErrorPropagation:
    """ProviderError from the provider propagates through write()."""

    def test_provider_error_propagates(self, tmp_path: Path) -> None:
        """A ProviderError raised by write_offline is not swallowed."""
        from unittest.mock import patch

        from kitefs.exceptions import ProviderError

        manager, provider, _ = _make_manager(tmp_path)
        df = _make_df(["2024-03-15"])

        with (
            patch.object(
                provider,
                "write_offline",
                side_effect=ProviderError("Disk full"),
            ),
            pytest.raises(ProviderError, match="Disk full"),
        ):
            manager.write("test_group", df, "event_timestamp")
