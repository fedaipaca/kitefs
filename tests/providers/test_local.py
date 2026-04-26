"""Tests for LocalProvider — read, write, and roundtrip."""

import os
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
from helpers import make_local_config
from pandas import DataFrame

from kitefs.config import Config
from kitefs.exceptions import ProviderError
from kitefs.providers import LocalProvider


class TestLocalProviderReadRegistry:
    """LocalProvider.read_registry — success and error paths."""

    def test_read_existing_registry_returns_content(self, tmp_path: Path) -> None:
        """Reading an existing registry.json returns its content."""
        config = make_local_config(tmp_path)
        config.storage_root.mkdir(parents=True)
        (config.storage_root / "registry.json").write_text('{"version": "1.0"}', encoding="utf-8")

        provider = LocalProvider(config)
        result = provider.read_registry()

        assert result == '{"version": "1.0"}'

    def test_read_missing_registry_raises_provider_error(self, tmp_path: Path) -> None:
        """Reading a non-existent registry.json raises ProviderError."""
        config = make_local_config(tmp_path)

        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match="Registry not found"):
            provider.read_registry()

    def test_missing_registry_error_mentions_kitefs_init(self, tmp_path: Path) -> None:
        """Missing registry error suggests running kitefs init."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match="kitefs init"):
            provider.read_registry()

    def test_missing_registry_error_mentions_path(self, tmp_path: Path) -> None:
        """Missing registry error includes the expected file path."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match=r"registry\.json"):
            provider.read_registry()

    def test_read_unreadable_file_raises_provider_error(self, tmp_path: Path) -> None:
        """A non-readable registry.json raises ProviderError."""
        if os.name == "nt":
            pytest.skip("File permission test is not reliable on Windows.")

        config = make_local_config(tmp_path)
        config.storage_root.mkdir(parents=True)
        registry = config.storage_root / "registry.json"
        registry.write_text('{"version": "1.0"}', encoding="utf-8")
        os.chmod(registry, 0o000)

        try:
            if os.access(registry, os.R_OK):
                pytest.skip("Could not make file non-readable in this environment.")

            provider = LocalProvider(config)
            with pytest.raises(ProviderError, match="Failed to read registry"):
                provider.read_registry()
        finally:
            os.chmod(registry, 0o644)


class TestLocalProviderWriteRegistry:
    """LocalProvider.write_registry — file creation, content, and directory creation."""

    def test_write_creates_registry_file(self, tmp_path: Path) -> None:
        """write_registry creates the registry.json file."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')

        assert (config.storage_root / "registry.json").exists()

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """write_registry creates missing parent directories."""
        config = make_local_config(tmp_path)
        assert not config.storage_root.exists()

        provider = LocalProvider(config)
        provider.write_registry('{"version": "1.0"}')

        assert config.storage_root.is_dir()

    def test_write_stores_exact_content(self, tmp_path: Path) -> None:
        """write_registry stores the exact string content provided."""
        config = make_local_config(tmp_path)
        data = '{\n  "version": "1.0",\n  "feature_groups": {}\n}'

        provider = LocalProvider(config)
        provider.write_registry(data)

        on_disk = (config.storage_root / "registry.json").read_text(encoding="utf-8")
        assert on_disk == data

    def test_write_overwrites_existing_content(self, tmp_path: Path) -> None:
        """write_registry overwrites the previous content."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')
        provider.write_registry('{"version": "2.0"}')

        on_disk = (config.storage_root / "registry.json").read_text(encoding="utf-8")
        assert on_disk == '{"version": "2.0"}'

    def test_write_registry_unwritable_directory_raises_provider_error(self, tmp_path: Path) -> None:
        """Writing to a non-writable directory raises ProviderError."""
        if os.name == "nt":
            pytest.skip("Permission-based directory write test is not reliable on Windows.")

        read_only_parent = tmp_path / "read_only_parent"
        read_only_parent.mkdir()
        original_mode = read_only_parent.stat().st_mode & 0o777
        os.chmod(read_only_parent, 0o555)

        try:
            if os.access(read_only_parent, os.W_OK):
                pytest.skip("Could not make directory non-writable in this environment.")

            storage_root = read_only_parent / "feature_store"
            config = Config(
                provider="local",
                project_root=tmp_path,
                storage_root=storage_root,
                definitions_path=storage_root / "definitions",
                aws=None,
            )
            provider = LocalProvider(config)

            with pytest.raises(ProviderError, match="Failed to write registry"):
                provider.write_registry('{"version": "1.0"}')
        finally:
            os.chmod(read_only_parent, original_mode)


class TestLocalProviderRegistryRoundtrip:
    """Read/write roundtrip — the provider does raw string I/O, no JSON interpretation."""

    def test_roundtrip_returns_exact_string(self, tmp_path: Path) -> None:
        """Write then read returns the exact same string."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        original = '{\n  "version": "1.0",\n  "feature_groups": {}\n}'

        provider.write_registry(original)
        result = provider.read_registry()

        assert result == original

    def test_roundtrip_preserves_unicode(self, tmp_path: Path) -> None:
        """Roundtrip preserves Unicode characters."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        data = '{"name": "café_features", "emoji": "🪁"}'

        provider.write_registry(data)

        assert provider.read_registry() == data

    def test_roundtrip_preserves_whitespace_and_formatting(self, tmp_path: Path) -> None:
        """Roundtrip preserves exact whitespace and JSON formatting."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        # Simulate deterministic JSON output as produced by the registry manager
        data = '{\n  "feature_groups": {},\n  "version": "1.0"\n}'

        provider.write_registry(data)

        assert provider.read_registry() == data

    def test_write_and_read_empty_string(self, tmp_path: Path) -> None:
        """Roundtrip of an empty string works."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry("")

        assert provider.read_registry() == ""

    def test_multiple_writes_last_write_wins(self, tmp_path: Path) -> None:
        """Multiple writes keep only the last written content."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')
        provider.write_registry('{"version": "1.1"}')
        provider.write_registry('{"version": "1.2"}')

        assert provider.read_registry() == '{"version": "1.2"}'


class TestLocalProviderWriteOffline:
    """LocalProvider.write_offline — directory creation, data integrity, append-only, atomicity."""

    def test_write_offline_creates_directory_structure(self, tmp_path: Path) -> None:
        """write_offline creates {storage_root}/data/offline_store/{group}/{partition}/{file}."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1], "value": [10.0]})

        provider.write_offline("listing_features", "year=2024/month=03", "test.parquet", df)

        expected = (
            config.storage_root
            / "data"
            / "offline_store"
            / "listing_features"
            / "year=2024"
            / "month=03"
            / "test.parquet"
        )
        assert expected.exists()
        table = pq.read_table(expected)
        assert table.num_rows == 1

    def test_write_offline_file_is_valid_parquet(self, tmp_path: Path) -> None:
        """Written file is readable by PyArrow and contains expected data."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1, 2], "name": ["a", "b"], "score": [1.5, 2.5]})

        provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

        path = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01" / "data.parquet"
        # Read via ParquetFile to avoid Hive-partition column inference
        result = pq.ParquetFile(path).read().to_pandas()
        assert list(result.columns) == ["id", "name", "score"]
        assert len(result) == 2
        assert list(result["id"]) == [1, 2]
        assert list(result["name"]) == ["a", "b"]

    def test_write_offline_append_only_coexistence(self, tmp_path: Path) -> None:
        """Two writes with different file names to the same partition both persist."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df1 = DataFrame({"id": [1], "value": [10.0]})
        df2 = DataFrame({"id": [2], "value": [20.0]})

        provider.write_offline("group", "year=2024/month=01", "file_a.parquet", df1)
        provider.write_offline("group", "year=2024/month=01", "file_b.parquet", df2)

        partition_dir = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01"
        parquet_files = sorted(partition_dir.glob("*.parquet"))
        assert len(parquet_files) == 2
        assert parquet_files[0].name == "file_a.parquet"
        assert parquet_files[1].name == "file_b.parquet"

    def test_write_offline_creates_parent_directories_lazily(self, tmp_path: Path) -> None:
        """write_offline creates all parent directories when none exist."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        offline_dir = config.storage_root / "data" / "offline_store"
        assert not offline_dir.exists()

        df = DataFrame({"id": [1]})
        provider.write_offline("new_group", "year=2025/month=06", "f.parquet", df)

        expected = offline_dir / "new_group" / "year=2025" / "month=06" / "f.parquet"
        assert expected.exists()

    def test_write_offline_realistic_file_name(self, tmp_path: Path) -> None:
        """Realistic file names like ing_20240315T120000_a1b2c3d4.parquet work correctly."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"listing_id": [1001], "sold_price": [2250000.0]})

        file_name = "ing_20240315T120000_a1b2c3d4.parquet"
        provider.write_offline("listing_features", "year=2024/month=03", file_name, df)

        expected = (
            config.storage_root / "data" / "offline_store" / "listing_features" / "year=2024" / "month=03" / file_name
        )
        assert expected.exists()

    def test_write_offline_preserves_dataframe_content(self, tmp_path: Path) -> None:
        """DataFrame with multiple columns and rows is roundtripped correctly via PyArrow."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame(
            {
                "listing_id": [1001, 1002, 1003],
                "net_area": [75, 120, 85],
                "sold_price": [2250000.0, 4800000.0, 1050000.0],
                "town": ["A", "B", "C"],
            }
        )

        provider.write_offline("group", "year=2024/month=03", "data.parquet", df)

        path = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=03" / "data.parquet"
        result = pq.read_table(path).to_pandas()
        assert list(result["listing_id"]) == [1001, 1002, 1003]
        assert list(result["net_area"]) == [75, 120, 85]
        assert list(result["sold_price"]) == [2250000.0, 4800000.0, 1050000.0]
        assert list(result["town"]) == ["A", "B", "C"]

    def test_write_offline_no_temp_files_remain_after_success(self, tmp_path: Path) -> None:
        """After a successful write, no .tmp files linger in the partition directory."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1]})

        provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

        partition_dir = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01"
        tmp_files = list(partition_dir.glob("*.tmp"))
        assert tmp_files == []

    def test_write_offline_empty_dataframe_creates_file(self, tmp_path: Path) -> None:
        """Writing an empty DataFrame still creates a valid Parquet file with zero rows."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [], "value": []})

        provider.write_offline("group", "year=2024/month=01", "empty.parquet", df)

        path = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01" / "empty.parquet"
        assert path.exists()
        table = pq.read_table(path)
        assert table.num_rows == 0

    def test_write_offline_unwritable_directory_raises_provider_error(self, tmp_path: Path) -> None:
        """Writing to a read-only parent directory raises ProviderError."""
        if os.name == "nt":
            pytest.skip("Permission-based directory write test is not reliable on Windows.")

        read_only_parent = tmp_path / "read_only_parent"
        read_only_parent.mkdir()
        original_mode = read_only_parent.stat().st_mode & 0o777
        os.chmod(read_only_parent, 0o555)

        try:
            if os.access(read_only_parent, os.W_OK):
                pytest.skip("Could not make directory non-writable in this environment.")

            storage_root = read_only_parent / "feature_store"
            config = Config(
                provider="local",
                project_root=tmp_path,
                storage_root=storage_root,
                definitions_path=storage_root / "definitions",
                aws=None,
            )
            provider = LocalProvider(config)
            df = DataFrame({"id": [1]})

            with pytest.raises(ProviderError, match="Failed to write offline"):
                provider.write_offline("group", "year=2024/month=01", "data.parquet", df)
        finally:
            os.chmod(read_only_parent, original_mode)

    def test_write_offline_provider_error_preserves_cause(self, tmp_path: Path) -> None:
        """ProviderError wraps the original exception via __cause__."""
        if os.name == "nt":
            pytest.skip("Permission-based directory write test is not reliable on Windows.")

        read_only_parent = tmp_path / "read_only_parent"
        read_only_parent.mkdir()
        original_mode = read_only_parent.stat().st_mode & 0o777
        os.chmod(read_only_parent, 0o555)

        try:
            if os.access(read_only_parent, os.W_OK):
                pytest.skip("Could not make directory non-writable in this environment.")

            storage_root = read_only_parent / "feature_store"
            config = Config(
                provider="local",
                project_root=tmp_path,
                storage_root=storage_root,
                definitions_path=storage_root / "definitions",
                aws=None,
            )
            provider = LocalProvider(config)
            df = DataFrame({"id": [1]})

            with pytest.raises(ProviderError) as exc_info:
                provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

            assert exc_info.value.__cause__ is not None
        finally:
            os.chmod(read_only_parent, original_mode)

    def test_write_offline_pyarrow_error_raises_provider_error(self, tmp_path: Path) -> None:
        """A DataFrame that PyArrow cannot convert raises ProviderError, not a raw ArrowException."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        # A column of custom objects that PyArrow cannot serialize
        df = DataFrame({"bad_col": [object(), object()]})

        with pytest.raises(ProviderError, match="Failed to write offline"):
            provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

    def test_write_offline_pyarrow_error_cleans_up_temp_file(self, tmp_path: Path) -> None:
        """When PyArrow conversion fails after mkstemp, the temp file is cleaned up."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"bad_col": [object(), object()]})

        with pytest.raises(ProviderError):
            provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

        partition_dir = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01"
        if partition_dir.exists():
            tmp_files = list(partition_dir.glob("*.tmp"))
            assert tmp_files == []

    def test_write_offline_same_file_name_overwrites_atomically(self, tmp_path: Path) -> None:
        """Writing twice with the same file name replaces the first via os.replace."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df1 = DataFrame({"id": [1], "value": [10.0]})
        df2 = DataFrame({"id": [2], "value": [20.0]})

        provider.write_offline("group", "year=2024/month=01", "same.parquet", df1)
        provider.write_offline("group", "year=2024/month=01", "same.parquet", df2)

        partition_dir = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01"
        parquet_files = list(partition_dir.glob("*.parquet"))
        assert len(parquet_files) == 1
        result = pq.read_table(parquet_files[0]).to_pandas()
        assert list(result["id"]) == [2]
        assert list(result["value"]) == [20.0]


class TestLocalProviderReadOffline:
    """LocalProvider.read_offline — data retrieval, combining, and graceful empty handling."""

    def test_read_offline_returns_data_from_single_partition(self, tmp_path: Path) -> None:
        """Reading from a single partition returns the correct DataFrame."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1, 2], "value": [10.0, 20.0]})
        provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

        result = provider.read_offline("group", ["year=2024/month=01"])

        assert len(result) == 2
        assert list(result["id"]) == [1, 2]
        assert list(result["value"]) == [10.0, 20.0]

    def test_read_offline_combines_data_from_multiple_partitions(self, tmp_path: Path) -> None:
        """Reading from multiple partitions combines all data into one DataFrame."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df1 = DataFrame({"id": [1], "value": [10.0]})
        df2 = DataFrame({"id": [2], "value": [20.0]})
        provider.write_offline("group", "year=2024/month=01", "a.parquet", df1)
        provider.write_offline("group", "year=2024/month=02", "b.parquet", df2)

        result = provider.read_offline("group", ["year=2024/month=01", "year=2024/month=02"])

        assert len(result) == 2
        assert sorted(result["id"].tolist()) == [1, 2]

    def test_read_offline_combines_multiple_files_in_same_partition(self, tmp_path: Path) -> None:
        """Multiple Parquet files in the same partition are all read and combined."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df1 = DataFrame({"id": [1], "value": [10.0]})
        df2 = DataFrame({"id": [2], "value": [20.0]})
        provider.write_offline("group", "year=2024/month=01", "file_a.parquet", df1)
        provider.write_offline("group", "year=2024/month=01", "file_b.parquet", df2)

        result = provider.read_offline("group", ["year=2024/month=01"])

        assert len(result) == 2
        assert sorted(result["id"].tolist()) == [1, 2]

    def test_read_offline_empty_partition_returns_empty_dataframe(self, tmp_path: Path) -> None:
        """A partition directory with no .parquet files returns an empty DataFrame."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        # Create the partition directory but don't write any Parquet files
        partition_dir = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01"
        partition_dir.mkdir(parents=True)

        result = provider.read_offline("group", ["year=2024/month=01"])

        assert isinstance(result, DataFrame)
        assert len(result) == 0

    def test_read_offline_nonexistent_partition_returns_empty_dataframe(self, tmp_path: Path) -> None:
        """A non-existent partition path returns an empty DataFrame, not an error."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        result = provider.read_offline("group", ["year=2099/month=12"])

        assert isinstance(result, DataFrame)
        assert len(result) == 0

    def test_read_offline_all_nonexistent_partitions_returns_empty_dataframe(self, tmp_path: Path) -> None:
        """Multiple non-existent partition paths all return an empty DataFrame."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        result = provider.read_offline("group", ["year=2099/month=01", "year=2099/month=02"])

        assert isinstance(result, DataFrame)
        assert len(result) == 0

    def test_read_offline_empty_partition_paths_list_returns_empty_dataframe(self, tmp_path: Path) -> None:
        """An empty partition_paths list returns an empty DataFrame."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        result = provider.read_offline("group", [])

        assert isinstance(result, DataFrame)
        assert len(result) == 0

    def test_read_offline_preserves_column_types(self, tmp_path: Path) -> None:
        """Column dtypes survive the write-then-read roundtrip."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1, 2], "name": ["a", "b"], "score": [1.5, 2.5]})
        provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

        result = provider.read_offline("group", ["year=2024/month=01"])

        assert result["id"].dtype.name == "int64"
        assert pd.api.types.is_string_dtype(result["name"])
        assert result["score"].dtype.name == "float64"

    def test_read_offline_unreadable_file_raises_provider_error(self, tmp_path: Path) -> None:
        """An unreadable Parquet file raises ProviderError."""
        if os.name == "nt":
            pytest.skip("Permission-based file read test is not reliable on Windows.")

        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1]})
        provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

        parquet_path = (
            config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01" / "data.parquet"
        )
        os.chmod(parquet_path, 0o000)

        try:
            if os.access(parquet_path, os.R_OK):
                pytest.skip("Could not make file non-readable in this environment.")

            with pytest.raises(ProviderError, match="Failed to read offline"):
                provider.read_offline("group", ["year=2024/month=01"])
        finally:
            os.chmod(parquet_path, 0o644)

    def test_read_offline_provider_error_preserves_cause(self, tmp_path: Path) -> None:
        """ProviderError wraps the original exception via __cause__."""
        if os.name == "nt":
            pytest.skip("Permission-based file read test is not reliable on Windows.")

        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1]})
        provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

        parquet_path = (
            config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01" / "data.parquet"
        )
        os.chmod(parquet_path, 0o000)

        try:
            if os.access(parquet_path, os.R_OK):
                pytest.skip("Could not make file non-readable in this environment.")

            with pytest.raises(ProviderError) as exc_info:
                provider.read_offline("group", ["year=2024/month=01"])

            assert exc_info.value.__cause__ is not None
        finally:
            os.chmod(parquet_path, 0o644)

    def test_read_offline_corrupted_parquet_raises_provider_error(self, tmp_path: Path) -> None:
        """A corrupted Parquet file raises ProviderError with an actionable message."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        partition_dir = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "month=01"
        partition_dir.mkdir(parents=True)
        (partition_dir / "corrupt.parquet").write_bytes(b"this is not a parquet file")

        with pytest.raises(ProviderError, match="Failed to read offline"):
            provider.read_offline("group", ["year=2024/month=01"])

    def test_read_offline_schema_mismatch_raises_provider_error(self, tmp_path: Path) -> None:
        """Files with incompatible schemas in one read raise ProviderError, not raw ArrowInvalid."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df1 = DataFrame({"id": [1], "value": [10.0]})
        df2 = DataFrame({"id": [2], "name": ["b"]})
        provider.write_offline("group", "year=2024/month=01", "a.parquet", df1)
        provider.write_offline("group", "year=2024/month=01", "b.parquet", df2)

        with pytest.raises(ProviderError, match="Failed to read offline"):
            provider.read_offline("group", ["year=2024/month=01"])

    def test_read_offline_mixed_existent_and_nonexistent_partitions(self, tmp_path: Path) -> None:
        """A mix of existing and non-existent partition paths returns only existing data."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1, 2], "value": [10.0, 20.0]})
        provider.write_offline("group", "year=2024/month=01", "data.parquet", df)

        result = provider.read_offline("group", ["year=2024/month=01", "year=2099/month=12"])

        assert len(result) == 2
        assert sorted(result["id"].tolist()) == [1, 2]


class TestLocalProviderListPartitions:
    """LocalProvider.list_partitions — discovery, sorting, and graceful empty handling."""

    def test_list_partitions_returns_paths_after_writes(self, tmp_path: Path) -> None:
        """list_partitions returns partition paths that have been written to."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1]})
        provider.write_offline("group", "year=2024/month=01", "a.parquet", df)
        provider.write_offline("group", "year=2024/month=03", "b.parquet", df)

        result = provider.list_partitions("group")

        assert result == ["year=2024/month=01", "year=2024/month=03"]

    def test_list_partitions_returns_empty_list_for_nonexistent_group(self, tmp_path: Path) -> None:
        """A group that was never written to returns an empty list."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        result = provider.list_partitions("nonexistent_group")

        assert result == []

    def test_list_partitions_unreadable_directory_raises_provider_error(self, tmp_path: Path) -> None:
        """An unreadable group directory raises ProviderError."""
        if os.name == "nt":
            pytest.skip("Permission-based directory read test is not reliable on Windows.")

        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        group_dir = config.storage_root / "data" / "offline_store" / "group"
        group_dir.mkdir(parents=True)
        # Create a valid year directory so iterdir() will be attempted
        (group_dir / "year=2024").mkdir()
        os.chmod(group_dir, 0o000)

        try:
            if os.access(group_dir, os.R_OK):
                pytest.skip("Could not make directory non-readable in this environment.")

            with pytest.raises(ProviderError, match="Failed to list partitions"):
                provider.list_partitions("group")
        finally:
            os.chmod(group_dir, 0o755)

    def test_list_partitions_results_are_sorted(self, tmp_path: Path) -> None:
        """Partition paths are returned in sorted order regardless of write order."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1]})
        # Write out of order
        provider.write_offline("group", "year=2024/month=12", "a.parquet", df)
        provider.write_offline("group", "year=2023/month=06", "b.parquet", df)
        provider.write_offline("group", "year=2024/month=01", "c.parquet", df)

        result = provider.list_partitions("group")

        assert result == ["year=2023/month=06", "year=2024/month=01", "year=2024/month=12"]

    def test_list_partitions_ignores_non_partition_directories(self, tmp_path: Path) -> None:
        """Directories not matching year=YYYY/month=MM are excluded."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1]})
        provider.write_offline("group", "year=2024/month=01", "a.parquet", df)

        # Create a rogue directory at the year level
        rogue_dir = config.storage_root / "data" / "offline_store" / "group" / "temp"
        rogue_dir.mkdir(parents=True)

        result = provider.list_partitions("group")

        assert result == ["year=2024/month=01"]

    def test_list_partitions_ignores_files_at_group_level(self, tmp_path: Path) -> None:
        """Files (not directories) at the group level are ignored."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1]})
        provider.write_offline("group", "year=2024/month=01", "a.parquet", df)

        # Create a rogue file at the group level
        rogue_file = config.storage_root / "data" / "offline_store" / "group" / "stray.txt"
        rogue_file.write_text("stray")

        result = provider.list_partitions("group")

        assert result == ["year=2024/month=01"]

    def test_list_partitions_returns_empty_for_group_dir_with_no_partitions(self, tmp_path: Path) -> None:
        """A group directory with no valid partition subdirectories returns empty list."""
        config = make_local_config(tmp_path)
        group_dir = config.storage_root / "data" / "offline_store" / "group"
        group_dir.mkdir(parents=True)

        provider = LocalProvider(config)
        result = provider.list_partitions("group")

        assert result == []

    def test_list_partitions_ignores_invalid_month_under_valid_year(self, tmp_path: Path) -> None:
        """A year=YYYY directory with a non-matching subdirectory is ignored."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"id": [1]})
        provider.write_offline("group", "year=2024/month=01", "a.parquet", df)

        # Create an invalid month directory under a valid year
        invalid_month = config.storage_root / "data" / "offline_store" / "group" / "year=2024" / "not_a_month"
        invalid_month.mkdir(parents=True)

        result = provider.list_partitions("group")

        assert result == ["year=2024/month=01"]


class TestLocalProviderOfflineRoundtrip:
    """End-to-end write → list → read roundtrip for the offline store."""

    def test_write_list_read_roundtrip(self, tmp_path: Path) -> None:
        """Data written to multiple partitions is fully recoverable via list + read."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df1 = DataFrame({"id": [1, 2], "value": [10.0, 20.0]})
        df2 = DataFrame({"id": [3, 4], "value": [30.0, 40.0]})
        provider.write_offline("group", "year=2024/month=01", "a.parquet", df1)
        provider.write_offline("group", "year=2024/month=06", "b.parquet", df2)

        partitions = provider.list_partitions("group")
        assert partitions == ["year=2024/month=01", "year=2024/month=06"]

        result = provider.read_offline("group", partitions)

        assert len(result) == 4
        assert sorted(result["id"].tolist()) == [1, 2, 3, 4]
        assert sorted(result["value"].tolist()) == [10.0, 20.0, 30.0, 40.0]

    def test_roundtrip_with_realistic_file_names(self, tmp_path: Path) -> None:
        """Roundtrip works with realistic ingestion-style file names."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        df = DataFrame({"listing_id": [1001, 1002], "sold_price": [2250000.0, 4800000.0]})
        provider.write_offline(
            "listing_features",
            "year=2024/month=03",
            "ing_20240315T120000_a1b2c3d4.parquet",
            df,
        )

        partitions = provider.list_partitions("listing_features")
        assert partitions == ["year=2024/month=03"]

        result = provider.read_offline("listing_features", partitions)

        assert len(result) == 2
        assert list(result["listing_id"]) == [1001, 1002]
        assert list(result["sold_price"]) == [2250000.0, 4800000.0]
