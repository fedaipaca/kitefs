"""Integration roundtrip tests — write then read through the OfflineStoreManager."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from helpers import make_local_config

from kitefs.offline_store import OfflineStoreManager
from kitefs.providers.local import LocalProvider


def _make_manager(tmp_path: Path) -> OfflineStoreManager:
    """Create an OfflineStoreManager backed by a LocalProvider in tmp_path."""
    config = make_local_config(tmp_path)
    config.storage_root.mkdir(parents=True, exist_ok=True)
    provider = LocalProvider(config)
    return OfflineStoreManager(provider)


class TestWriteReadRoundtrip:
    """Write data and read it back — verify data integrity."""

    def test_roundtrip_unfiltered(self, tmp_path: Path) -> None:
        """Write and read back all data without filtering."""
        manager = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "listing_id": [1001, 1002, 1003],
                "event_timestamp": pd.to_datetime(
                    [
                        "2024-03-15 11:00:00",
                        "2024-03-18 14:30:00",
                        "2024-04-02 09:00:00",
                    ]
                ),
                "sold_price": [2250000.0, 1050000.0, 3100000.0],
            }
        )

        manager.write("listing_features", df, "event_timestamp")
        result = manager.read("listing_features", "event_timestamp")

        assert len(result) == 3
        assert set(result.columns) == {"listing_id", "event_timestamp", "sold_price"}
        assert sorted(result["listing_id"].tolist()) == [1001, 1002, 1003]

    def test_roundtrip_with_time_range(self, tmp_path: Path) -> None:
        """Write data spanning multiple months, read back a specific time range."""
        manager = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "id": list(range(1, 7)),
                "event_timestamp": pd.to_datetime(
                    [
                        "2024-01-15",
                        "2024-02-10",
                        "2024-03-05",
                        "2024-04-20",
                        "2024-05-12",
                        "2024-06-01",
                    ]
                ),
                "value": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
            }
        )

        manager.write("test_group", df, "event_timestamp")
        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={
                "gte": datetime(2024, 3, 1),
                "lt": datetime(2024, 5, 1),
            },
        )

        assert len(result) == 2
        assert sorted(result["id"].tolist()) == [3, 4]

    def test_multiple_writes_combined_read(self, tmp_path: Path) -> None:
        """Multiple append-only writes are combined in a single read."""
        manager = _make_manager(tmp_path)

        batch1 = pd.DataFrame(
            {
                "id": [1, 2],
                "event_timestamp": pd.to_datetime(["2024-03-15", "2024-03-20"]),
                "value": [10.0, 20.0],
            }
        )
        batch2 = pd.DataFrame(
            {
                "id": [3, 4],
                "event_timestamp": pd.to_datetime(["2024-03-25", "2024-04-01"]),
                "value": [30.0, 40.0],
            }
        )

        manager.write("test_group", batch1, "event_timestamp")
        manager.write("test_group", batch2, "event_timestamp")

        result = manager.read("test_group", "event_timestamp")

        assert len(result) == 4
        assert sorted(result["id"].tolist()) == [1, 2, 3, 4]

    def test_roundtrip_preserves_data_types(self, tmp_path: Path) -> None:
        """Data types survive the write→read roundtrip."""
        manager = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "id": pd.array([1, 2], dtype="int64"),
                "event_timestamp": pd.to_datetime(["2024-03-15", "2024-03-20"]),
                "price": pd.array([2250000.5, 1050000.0], dtype="float64"),
                "label": ["sold", "pending"],
            }
        )

        manager.write("test_group", df, "event_timestamp")
        result = manager.read("test_group", "event_timestamp")

        assert result["id"].dtype == "int64"
        assert result["price"].dtype == "float64"
        assert pd.api.types.is_datetime64_any_dtype(result["event_timestamp"])

    def test_full_group_read_for_materialization(self, tmp_path: Path) -> None:
        """Read with no filters returns everything — the materialization path."""
        manager = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "town_id": [1, 2, 3, 1, 2, 3],
                "event_timestamp": pd.to_datetime(
                    [
                        "2024-01-01",
                        "2024-01-01",
                        "2024-01-01",
                        "2024-02-01",
                        "2024-02-01",
                        "2024-02-01",
                    ]
                ),
                "avg_price": [24500.0, 28200.0, 14100.0, 25000.0, 29000.0, 14500.0],
            }
        )

        manager.write("town_market_features", df, "event_timestamp")
        result = manager.read("town_market_features", "event_timestamp")

        assert len(result) == 6
        assert set(result["town_id"].tolist()) == {1, 2, 3}

    def test_roundtrip_with_upper_bound(self, tmp_path: Path) -> None:
        """Read with upper_bound prunes future partitions."""
        manager = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "event_timestamp": pd.to_datetime(
                    [
                        "2024-01-15",
                        "2024-06-10",
                        "2024-12-01",
                    ]
                ),
                "value": [10.0, 20.0, 30.0],
            }
        )

        manager.write("test_group", df, "event_timestamp")
        result = manager.read(
            "test_group",
            "event_timestamp",
            upper_bound=datetime(2024, 6, 15),
        )

        # Partitions month=01 and month=06 included, month=12 pruned.
        assert len(result) == 2
        assert sorted(result["id"].tolist()) == [1, 2]

    def test_roundtrip_with_naive_timestamps(self, tmp_path: Path) -> None:
        """Write timezone-naive timestamps and read them back correctly."""
        manager = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "event_timestamp": pd.to_datetime(["2024-03-15", "2024-03-20", "2024-04-02"]),
                "value": [10.0, 20.0, 30.0],
            }
        )

        manager.write("test_group", df, "event_timestamp")
        result = manager.read("test_group", "event_timestamp")

        assert len(result) == 3
        assert sorted(result["id"].tolist()) == [1, 2, 3]

    def test_roundtrip_with_naive_filter(self, tmp_path: Path) -> None:
        """Write timezone-naive data and filter with timezone-naive boundaries."""
        manager = _make_manager(tmp_path)
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "event_timestamp": pd.to_datetime(["2024-01-15", "2024-03-10", "2024-06-01"]),
                "value": [10.0, 20.0, 30.0],
            }
        )

        manager.write("test_group", df, "event_timestamp")
        result = manager.read(
            "test_group",
            "event_timestamp",
            time_filter={
                "gte": datetime(2024, 2, 1),
                "lte": datetime(2024, 4, 1),
            },
        )

        assert len(result) == 1
        assert result.iloc[0]["id"] == 2
