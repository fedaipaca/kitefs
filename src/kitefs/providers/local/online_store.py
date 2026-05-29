"""Local SQLite-backed online store implementation.

Each online-capable feature group gets its own table inside a single SQLite
database at:

    {root}/feature_store/data/online_store/online.db

Every connection enables WAL mode for concurrent reader safety and sets a
busy_timeout so contention doesn't cause immediate failures.

Materialization is atomic per group: a single transaction deletes all existing
rows and inserts the new latest-row set. On any error the transaction is rolled
back, leaving the prior committed contents intact.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa

from kitefs.enums import FeatureType
from kitefs.errors import OnlineStoreWriteError, format_actionable
from kitefs.providers.base import OnlineStore

# Mapping from KiteFS FeatureType to SQLite type affinity.
_FEATURE_TYPE_TO_SQLITE: dict[FeatureType, str] = {
    FeatureType.STRING: "TEXT",
    FeatureType.INTEGER: "INTEGER",
    FeatureType.FLOAT: "REAL",
    FeatureType.DATETIME: "TEXT",
}


def _sqlite_type(feature_type: FeatureType) -> str:
    return _FEATURE_TYPE_TO_SQLITE[feature_type]


def _serialize_value(value: Any, col_index: int, schema: pa.Schema) -> Any:
    """Convert a pyarrow-typed Python value to a SQLite-compatible scalar.

    Datetimes are serialized as ISO-8601 UTC strings:
        "YYYY-MM-DDTHH:MM:SS.ffffffZ"
    Null values pass through as None (SQLite NULL).
    All other types are passed through unchanged.
    """
    if value is None:
        return None
    arrow_type = schema.field(col_index).type
    if pa.types.is_timestamp(arrow_type):
        # value may be a datetime or pandas Timestamp; normalize to datetime
        if not isinstance(value, datetime):
            import pandas as pd

            value = pd.Timestamp(value).to_pydatetime()
        # Ensure UTC; treat naive as UTC per the datetime contract
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return value


class LocalOnlineStore(OnlineStore):
    """SQLite online store for local deployments."""

    def __init__(self, root: Path) -> None:
        self._db_path = root / "feature_store" / "data" / "online_store" / "online.db"

    def _connect(self) -> sqlite3.Connection:
        """Open a connection to the SQLite database with WAL mode enabled."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def materialize(
        self,
        feature_group: str,
        latest_rows: pa.Table,
        *,
        entity_key_column: str,
    ) -> None:
        """Atomically replace the online table for *feature_group*.

        Creates the per-group table if it does not yet exist, then within a
        single transaction: deletes all existing rows and inserts *latest_rows*.
        On any error the transaction is rolled back and an OnlineStoreWriteError
        is raised, leaving the prior committed contents intact.

        The *entity_key_column* is the PRIMARY KEY of the table. All other
        columns from *latest_rows* are stored in declaration order.

        FeatureType → SQLite affinity mapping:
            STRING  → TEXT
            INTEGER → INTEGER
            FLOAT   → REAL
            DATETIME → TEXT  (serialized as ISO-8601 UTC string)
        """
        schema = latest_rows.schema
        n_cols = len(schema)

        # Build column definitions for CREATE TABLE.
        # The entity key column gets the PRIMARY KEY constraint.
        col_defs: list[str] = []
        for i in range(n_cols):
            field = schema.field(i)
            name = field.name
            # Infer SQLite affinity from the PyArrow type.
            arrow_type = field.type
            if pa.types.is_integer(arrow_type):
                sqlite_type = "INTEGER"
            elif pa.types.is_floating(arrow_type):
                sqlite_type = "REAL"
            elif (
                pa.types.is_large_string(arrow_type)
                or pa.types.is_string(arrow_type)
                or pa.types.is_timestamp(arrow_type)
            ):
                sqlite_type = "TEXT"
            else:
                # fallback to TEXT for all other types (boolean, binary, etc.)
                sqlite_type = "TEXT"

            if name == entity_key_column:
                col_defs.append(f'"{name}" {sqlite_type} PRIMARY KEY')
            else:
                col_defs.append(f'"{name}" {sqlite_type} NOT NULL')

        ddl = f'CREATE TABLE IF NOT EXISTS "{feature_group}" ({", ".join(col_defs)})'

        # Prepare the INSERT statement.
        placeholders = ", ".join("?" * n_cols)
        insert_sql = f'INSERT INTO "{feature_group}" VALUES ({placeholders})'

        # Serialize all rows to Python tuples for executemany.
        rows: list[tuple[Any, ...]] = []
        col_arrays = [latest_rows.column(i).to_pylist() for i in range(n_cols)]
        for row_idx in range(len(latest_rows)):
            row = tuple(_serialize_value(col_arrays[col_idx][row_idx], col_idx, schema) for col_idx in range(n_cols))
            rows.append(row)

        conn = self._connect()
        try:
            conn.execute(ddl)
            conn.execute("BEGIN")
            conn.execute(f'DELETE FROM "{feature_group}"')
            conn.executemany(insert_sql, rows)
            conn.execute("COMMIT")
        except Exception as exc:
            import contextlib

            with contextlib.suppress(Exception):
                conn.execute("ROLLBACK")
            raise OnlineStoreWriteError(
                format_actionable(
                    group=feature_group,
                    problem=f"SQLite write failed: {exc}",
                    next_step="check disk space and permissions for the online store database",
                )
            ) from exc
        finally:
            conn.close()

    def get(
        self,
        feature_group: str,
        entity_key_value: str | int,
        *,
        entity_key_column: str,
        select: list[str] | None,
    ) -> dict[str, Any]:
        """Not implemented — online retrieval lands in Feature 11."""
        raise NotImplementedError("Local online store retrieval lands in Feature 11")


__all__ = ["LocalOnlineStore"]
