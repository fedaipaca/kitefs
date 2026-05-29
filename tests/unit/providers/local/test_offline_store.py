"""Unit tests for LocalOfflineStore."""

from __future__ import annotations

import datetime
from pathlib import Path

import pyarrow as pa
import pytest

from kitefs.errors import OfflineStoreWriteError
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


class TestRead:
    """LocalOfflineStore.read() raises NotImplementedError in Feature 7."""

    def test_raises_not_implemented(self, tmp_path: Path) -> None:
        """read() is not yet implemented and raises NotImplementedError."""
        store = LocalOfflineStore(tmp_path)

        with pytest.raises(NotImplementedError):
            store.read("town_market_features", event_timestamp_column="event_timestamp", schema=pa.schema([]))
