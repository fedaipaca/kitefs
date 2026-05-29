"""Unit tests for kitefs.online_store.select_latest_rows."""

from __future__ import annotations

from datetime import UTC, datetime

import pyarrow as pa
import pytest

from kitefs.online_store import select_latest_rows


def _ts(dt_str: str) -> datetime:
    """Parse a UTC datetime string to an aware datetime."""
    return datetime.fromisoformat(dt_str).replace(tzinfo=UTC)


def _table(rows: list[dict]) -> pa.Table:
    """Build a small test table from a list of dicts with entity_id and ts keys."""
    entity_ids = pa.array([r["entity_id"] for r in rows], type=pa.int64())
    timestamps = pa.array(
        [_ts(r["ts"]) for r in rows],
        type=pa.timestamp("us", tz="UTC"),
    )
    extras = pa.array([r.get("value", 0) for r in rows], type=pa.float64())
    return pa.table({"entity_id": entity_ids, "ts": timestamps, "value": extras})


class TestSelectLatestRows:
    """select_latest_rows returns one row per entity key with the latest event timestamp."""

    def test_empty_table_returns_empty(self) -> None:
        """Empty input returns an empty table with the same schema."""
        schema = pa.schema([("entity_id", pa.int64()), ("ts", pa.timestamp("us", tz="UTC")), ("value", pa.float64())])
        empty = schema.empty_table()
        result = select_latest_rows(empty, entity_key_column="entity_id", event_timestamp_column="ts")
        assert len(result) == 0
        assert result.schema == schema

    def test_single_row_returns_single_row(self) -> None:
        """A table with one row returns that row unchanged."""
        t = _table([{"entity_id": 1, "ts": "2024-01-01T00:00:00"}])
        result = select_latest_rows(t, entity_key_column="entity_id", event_timestamp_column="ts")
        assert len(result) == 1
        assert result.column("entity_id")[0].as_py() == 1

    def test_distinct_entities_all_returned(self) -> None:
        """One row per distinct entity is returned when all timestamps differ."""
        t = _table(
            [
                {"entity_id": 1, "ts": "2024-01-01T00:00:00"},
                {"entity_id": 2, "ts": "2024-02-01T00:00:00"},
                {"entity_id": 3, "ts": "2024-03-01T00:00:00"},
            ]
        )
        result = select_latest_rows(t, entity_key_column="entity_id", event_timestamp_column="ts")
        assert len(result) == 3

    def test_latest_timestamp_wins(self) -> None:
        """When the same entity has multiple rows, the row with max timestamp is kept."""
        t = _table(
            [
                {"entity_id": 1, "ts": "2024-01-01T00:00:00", "value": 10.0},
                {"entity_id": 1, "ts": "2024-06-01T00:00:00", "value": 20.0},
                {"entity_id": 1, "ts": "2024-03-01T00:00:00", "value": 15.0},
            ]
        )
        result = select_latest_rows(t, entity_key_column="entity_id", event_timestamp_column="ts")
        assert len(result) == 1
        assert result.column("value")[0].as_py() == pytest.approx(20.0)

    def test_tie_broken_by_later_ingest_row(self) -> None:
        """Equal timestamps: the later-positioned row in the input table wins."""
        t = _table(
            [
                {"entity_id": 1, "ts": "2024-06-01T00:00:00", "value": 10.0},
                {"entity_id": 1, "ts": "2024-06-01T00:00:00", "value": 99.0},  # same ts, later position
            ]
        )
        result = select_latest_rows(t, entity_key_column="entity_id", event_timestamp_column="ts")
        assert len(result) == 1
        assert result.column("value")[0].as_py() == pytest.approx(99.0)

    def test_mixed_entities_and_timestamps(self) -> None:
        """Returns exactly one latest row per entity from a mixed input."""
        t = _table(
            [
                {"entity_id": 1, "ts": "2024-01-01T00:00:00", "value": 1.0},
                {"entity_id": 2, "ts": "2024-01-01T00:00:00", "value": 2.0},
                {"entity_id": 1, "ts": "2024-06-01T00:00:00", "value": 10.0},
                {"entity_id": 2, "ts": "2024-03-01T00:00:00", "value": 20.0},
                {"entity_id": 1, "ts": "2024-03-01T00:00:00", "value": 5.0},
            ]
        )
        result = select_latest_rows(t, entity_key_column="entity_id", event_timestamp_column="ts")
        assert len(result) == 2
        vals = {row["entity_id"]: row["value"] for row in result.to_pylist()}
        assert vals[1] == pytest.approx(10.0)
        assert vals[2] == pytest.approx(20.0)

    def test_output_schema_matches_input(self) -> None:
        """Output schema equals input schema (no extra columns)."""
        t = _table([{"entity_id": 1, "ts": "2024-01-01T00:00:00", "value": 5.0}])
        result = select_latest_rows(t, entity_key_column="entity_id", event_timestamp_column="ts")
        assert result.schema == t.schema
