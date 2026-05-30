"""Unit tests for LocalOfflineStore."""

from __future__ import annotations

import datetime
from pathlib import Path

import pyarrow as pa
import pytest

from kitefs.errors import OfflineStoreReadError, OfflineStoreWriteError
from kitefs.providers.base import TimestampFilter
from kitefs.providers.local.offline_store import LocalOfflineStore

_UTC = datetime.UTC
_TS_FEB = datetime.datetime(2024, 2, 1, tzinfo=_UTC)
_TS_MAR = datetime.datetime(2024, 3, 1, tzinfo=_UTC)


def _small_table(timestamps: list[datetime.datetime]) -> pa.Table:
    """Build a minimal pa.Table with town_id, event_timestamp, avg_price_per_sqm."""
    naive_ts = [ts.replace(tzinfo=None) for ts in timestamps]
    return pa.table(
        {
            "town_id": pa.array([i + 1 for i in range(len(naive_ts))], type=pa.int64()),
            "event_timestamp": pa.array(naive_ts, type=pa.timestamp("us")),
            "avg_price_per_sqm": pa.array([float(20000 + i * 100) for i in range(len(naive_ts))], type=pa.float64()),
        }
    )


class TestWrite:
    """LocalOfflineStore.write() stores Parquet files in Hive-partitioned layout."""

    def test_creates_hive_partition_directory(self, tmp_path: Path) -> None:
        """A single partition directory is created under offline_store/{group}/year=/month=."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB])

        store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        expected = (
            tmp_path / "feature_store" / "data" / "offline_store" / "town_market_features" / "year=2024" / "month=02"
        )
        assert expected.is_dir()

    def test_returns_absolute_paths(self, tmp_path: Path) -> None:
        """write() returns a list of absolute path strings, one per partition."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB])

        written = store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        assert len(written) == 1
        assert Path(written[0]).is_absolute()
        assert Path(written[0]).exists()

    def test_file_name_starts_with_source_prefix(self, tmp_path: Path) -> None:
        """write() names each file with the source_prefix at the start."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB])

        written = store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        assert Path(written[0]).name.startswith("ing_")

    def test_multi_month_produces_two_files(self, tmp_path: Path) -> None:
        """Rows spanning two months produce one file per month."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB, _TS_MAR])

        written = store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        assert len(written) == 2
        names = {Path(p).parent.name for p in written}
        assert names == {"month=02", "month=03"}

    def test_append_does_not_delete_existing_files(self, tmp_path: Path) -> None:
        """A second write to the same partition does not remove the first file."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB])

        first = store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )
        second = store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        assert len(first) == 1
        assert len(second) == 1
        assert Path(first[0]).exists(), "first file was deleted by second write"
        assert Path(second[0]).exists()
        assert first[0] != second[0]

    def test_no_temp_file_left_on_success(self, tmp_path: Path) -> None:
        """No .tmp_ file remains after a successful write."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB])

        store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        offline_root = tmp_path / "feature_store" / "data" / "offline_store"
        tmp_files = list(offline_root.rglob(".tmp_*"))
        assert tmp_files == []

    def test_raises_offline_store_write_error_on_io_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OfflineStoreWriteError is raised when the physical write fails."""
        import pyarrow.parquet as pq

        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB])

        def _boom(*_args, **_kwargs) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(pq, "write_table", _boom)

        with pytest.raises(OfflineStoreWriteError):
            store.write("town_market_features", table, event_timestamp_column="event_timestamp", source_prefix="ing")

    def test_no_partial_file_visible_after_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No final-path file exists when the write raises."""
        import contextlib

        import pyarrow.parquet as pq

        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB])

        monkeypatch.setattr(pq, "write_table", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))

        with contextlib.suppress(OfflineStoreWriteError):
            store.write(
                "town_market_features",
                table,
                event_timestamp_column="event_timestamp",
                source_prefix="ing",
            )

        offline_root = tmp_path / "feature_store" / "data" / "offline_store"
        parquet_files = list(offline_root.rglob("*.parquet")) if offline_root.exists() else []
        assert parquet_files == []


# Schema used for all read tests: matches _small_table() columns.
_READ_SCHEMA = pa.schema(
    [
        pa.field("town_id", pa.int64()),
        pa.field("event_timestamp", pa.timestamp("us")),
        pa.field("avg_price_per_sqm", pa.float64()),
    ]
)


class TestRead:
    """LocalOfflineStore.read() returns feature rows from Hive-partitioned Parquet."""

    def test_missing_group_dir_returns_empty_table(self, tmp_path: Path) -> None:
        """read() returns an empty schema-conforming table when the group has never been ingested."""
        store = LocalOfflineStore(tmp_path)

        result = store.read(
            "town_market_features",
            event_timestamp_column="event_timestamp",
            schema=_READ_SCHEMA,
        )

        assert len(result) == 0
        assert result.schema.equals(_READ_SCHEMA)

    def test_read_returns_written_rows(self, tmp_path: Path) -> None:
        """read() returns all ingested rows without the Hive partition columns."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB, _TS_MAR])
        store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        result = store.read(
            "town_market_features",
            event_timestamp_column="event_timestamp",
            schema=_READ_SCHEMA,
        )

        assert len(result) == 2
        assert set(result.schema.names) == {"town_id", "event_timestamp", "avg_price_per_sqm"}
        # Partition columns (year, month) must not appear in the output.
        assert "year" not in result.schema.names
        assert "month" not in result.schema.names

    def test_gte_filter_excludes_earlier_rows(self, tmp_path: Path) -> None:
        """A gte timestamp filter returns only rows on or after the bound."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB, _TS_MAR])
        store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        result = store.read(
            "town_market_features",
            event_timestamp_column="event_timestamp",
            schema=_READ_SCHEMA,
            timestamp_filter=TimestampFilter(gte=_TS_MAR),
        )

        assert len(result) == 1
        row_ts = result.column("event_timestamp")[0].as_py()
        assert row_ts == _TS_MAR.replace(tzinfo=None)

    def test_lte_filter_excludes_later_rows(self, tmp_path: Path) -> None:
        """A lte timestamp filter returns only rows on or before the bound."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB, _TS_MAR])
        store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        result = store.read(
            "town_market_features",
            event_timestamp_column="event_timestamp",
            schema=_READ_SCHEMA,
            timestamp_filter=TimestampFilter(lte=_TS_FEB),
        )

        assert len(result) == 1
        row_ts = result.column("event_timestamp")[0].as_py()
        assert row_ts == _TS_FEB.replace(tzinfo=None)

    def test_filter_matching_no_rows_returns_empty_table(self, tmp_path: Path) -> None:
        """A filter range with no matching rows returns an empty schema-conforming table."""
        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB, _TS_MAR])
        store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )
        far_future = datetime.datetime(2099, 1, 1, tzinfo=_UTC)

        result = store.read(
            "town_market_features",
            event_timestamp_column="event_timestamp",
            schema=_READ_SCHEMA,
            timestamp_filter=TimestampFilter(gte=far_future),
        )

        assert len(result) == 0
        assert result.schema.equals(_READ_SCHEMA)

    def test_unfiltered_read_failure_raises_offline_store_read_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A physical read failure in the unfiltered path is wrapped as OfflineStoreReadError."""
        import pyarrow.parquet as pq

        store = LocalOfflineStore(tmp_path)
        table = _small_table([_TS_FEB])
        store.write(
            "town_market_features",
            table,
            event_timestamp_column="event_timestamp",
            source_prefix="ing",
        )

        def _fail(*args: object, **kwargs: object) -> object:
            raise OSError("disk error")

        monkeypatch.setattr(pq, "read_table", _fail)

        with pytest.raises(OfflineStoreReadError):
            store.read(
                "town_market_features",
                event_timestamp_column="event_timestamp",
                schema=_READ_SCHEMA,
            )
