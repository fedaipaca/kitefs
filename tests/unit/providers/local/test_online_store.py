"""Unit tests for kitefs.providers.local.online_store.LocalOnlineStore."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pytest

from kitefs.providers.local.online_store import LocalOnlineStore


def _ts(dt_str: str) -> datetime:
    """Parse an ISO UTC datetime string."""
    return datetime.fromisoformat(dt_str).replace(tzinfo=UTC)


def _market_table(rows: list[dict]) -> pa.Table:
    """Build a minimal market-features table matching the local store schema."""
    town_ids = pa.array([r["town_id"] for r in rows], type=pa.int64())
    timestamps = pa.array([_ts(r["ts"]) for r in rows], type=pa.timestamp("us", tz="UTC"))
    prices = pa.array([r["price"] for r in rows], type=pa.float64())
    return pa.table({"town_id": town_ids, "event_timestamp": timestamps, "avg_price": prices})


class TestMaterialize:
    """LocalOnlineStore.materialize() creates and replaces the per-group SQLite table."""

    def test_creates_database_file(self, tmp_path: Path) -> None:
        """materialize() creates the SQLite database file if it does not exist."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table([{"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 10.0}])
        store.materialize("tmf", t, entity_key_column="town_id")
        expected_db = tmp_path / "feature_store" / "data" / "online_store" / "online.db"
        assert expected_db.exists()

    def test_table_has_expected_row_count(self, tmp_path: Path) -> None:
        """Rows written equal the number of rows in the latest_rows table."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table(
            [
                {"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 10.0},
                {"town_id": 2, "ts": "2024-01-01T00:00:00", "price": 20.0},
                {"town_id": 3, "ts": "2024-01-01T00:00:00", "price": 30.0},
            ]
        )
        store.materialize("tmf", t, entity_key_column="town_id")
        db_path = tmp_path / "feature_store" / "data" / "online_store" / "online.db"
        with sqlite3.connect(str(db_path)) as conn:
            count = conn.execute('SELECT COUNT(*) FROM "tmf"').fetchone()[0]
        assert count == 3

    def test_entity_key_is_primary_key(self, tmp_path: Path) -> None:
        """The entity key column is the PRIMARY KEY — duplicate keys overwrite."""
        store = LocalOnlineStore(tmp_path)
        t1 = _market_table([{"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 10.0}])
        store.materialize("tmf", t1, entity_key_column="town_id")
        # Second call replaces the table entirely (DELETE + INSERT).
        t2 = _market_table([{"town_id": 1, "ts": "2024-06-01T00:00:00", "price": 99.0}])
        store.materialize("tmf", t2, entity_key_column="town_id")
        db_path = tmp_path / "feature_store" / "data" / "online_store" / "online.db"
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute('SELECT avg_price FROM "tmf"').fetchall()
        assert len(rows) == 1
        assert rows[0][0] == pytest.approx(99.0)

    def test_second_call_replaces_all_rows(self, tmp_path: Path) -> None:
        """A second materialize() call fully replaces the prior contents."""
        store = LocalOnlineStore(tmp_path)
        t1 = _market_table(
            [
                {"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 10.0},
                {"town_id": 2, "ts": "2024-01-01T00:00:00", "price": 20.0},
            ]
        )
        store.materialize("tmf", t1, entity_key_column="town_id")
        t2 = _market_table([{"town_id": 1, "ts": "2024-06-01T00:00:00", "price": 50.0}])
        store.materialize("tmf", t2, entity_key_column="town_id")
        db_path = tmp_path / "feature_store" / "data" / "online_store" / "online.db"
        with sqlite3.connect(str(db_path)) as conn:
            count = conn.execute('SELECT COUNT(*) FROM "tmf"').fetchone()[0]
        assert count == 1

    def test_datetime_serialized_as_iso_string(self, tmp_path: Path) -> None:
        """DATETIME columns are stored as ISO-8601 UTC strings ending in Z."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table([{"town_id": 1, "ts": "2025-01-01T00:00:00", "price": 5.0}])
        store.materialize("tmf", t, entity_key_column="town_id")
        db_path = tmp_path / "feature_store" / "data" / "online_store" / "online.db"
        with sqlite3.connect(str(db_path)) as conn:
            ts_str = conn.execute('SELECT event_timestamp FROM "tmf"').fetchone()[0]
        assert ts_str == "2025-01-01T00:00:00.000000Z"

    def test_empty_table_leaves_table_empty(self, tmp_path: Path) -> None:
        """Materializing an empty table leaves the group table with zero rows."""
        store = LocalOnlineStore(tmp_path)
        schema = pa.schema(
            [
                ("town_id", pa.int64()),
                ("event_timestamp", pa.timestamp("us", tz="UTC")),
                ("avg_price", pa.float64()),
            ]
        )
        empty = schema.empty_table()
        store.materialize("tmf", empty, entity_key_column="town_id")
        db_path = tmp_path / "feature_store" / "data" / "online_store" / "online.db"
        with sqlite3.connect(str(db_path)) as conn:
            count = conn.execute('SELECT COUNT(*) FROM "tmf"').fetchone()[0]
        assert count == 0

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """materialize() creates the online_store directory if missing."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table([{"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 1.0}])
        store.materialize("tmf", t, entity_key_column="town_id")
        assert (tmp_path / "feature_store" / "data" / "online_store").is_dir()


class TestGet:
    """LocalOnlineStore.get() performs a SQLite primary-key lookup."""

    def test_hit_returns_row_as_dict(self, tmp_path: Path) -> None:
        """get() returns a dict with the matching row values on hit."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table([{"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 27800.0}])
        store.materialize("tmf", t, entity_key_column="town_id")
        result = store.get("tmf", 1, entity_key_column="town_id", select=["town_id", "event_timestamp", "avg_price"])
        assert result["town_id"] == 1
        assert result["avg_price"] == pytest.approx(27800.0)

    def test_miss_returns_empty_dict(self, tmp_path: Path) -> None:
        """get() returns {} when entity key value has no matching row."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table([{"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 10.0}])
        store.materialize("tmf", t, entity_key_column="town_id")
        result = store.get("tmf", 999, entity_key_column="town_id", select=["town_id", "event_timestamp", "avg_price"])
        assert result == {}

    def test_missing_table_returns_empty_dict(self, tmp_path: Path) -> None:
        """get() returns {} when the group's table has never been materialized."""
        store = LocalOnlineStore(tmp_path)
        result = store.get("nonexistent", 1, entity_key_column="town_id", select=None)
        assert result == {}

    def test_select_none_returns_all_columns(self, tmp_path: Path) -> None:
        """select=None returns all columns from the table."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table([{"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 10.0}])
        store.materialize("tmf", t, entity_key_column="town_id")
        result = store.get("tmf", 1, entity_key_column="town_id", select=None)
        assert set(result.keys()) == {"town_id", "event_timestamp", "avg_price"}

    def test_select_filters_columns(self, tmp_path: Path) -> None:
        """select restricts the returned columns to those specified."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table([{"town_id": 1, "ts": "2024-01-01T00:00:00", "price": 10.0}])
        store.materialize("tmf", t, entity_key_column="town_id")
        result = store.get("tmf", 1, entity_key_column="town_id", select=["town_id", "avg_price"])
        assert set(result.keys()) == {"town_id", "avg_price"}
        assert "event_timestamp" not in result

    def test_datetime_column_returned_as_string(self, tmp_path: Path) -> None:
        """Datetime columns are returned as ISO-8601 strings (SDK coerces to datetime)."""
        store = LocalOnlineStore(tmp_path)
        t = _market_table([{"town_id": 1, "ts": "2025-06-01T00:00:00", "price": 5.0}])
        store.materialize("tmf", t, entity_key_column="town_id")
        result = store.get("tmf", 1, entity_key_column="town_id", select=["event_timestamp"])
        assert isinstance(result["event_timestamp"], str)
        assert result["event_timestamp"].startswith("2025-06-01")
