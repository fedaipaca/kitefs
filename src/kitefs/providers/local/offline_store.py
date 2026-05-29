"""Local filesystem-backed offline store implementation.

Writes Hive-partitioned Parquet files to:
    {root}/feature_store/data/offline_store/{group}/year=YYYY/month=MM/

Each write is atomic: the Parquet payload is written to a sibling temp file
in the destination partition directory and then installed with os.replace().
Partial files are never visible at the final path.

File naming:
    {source_prefix}_{YYYYMMDDTHHMMSS}_{short_id}.parquet

where YYYYMMDDTHHMMSS is the UTC wall-clock time of the write (second
precision) and short_id is uuid4().hex[:6] for collision resistance.
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from kitefs.errors import OfflineStoreWriteError, format_actionable
from kitefs.providers.base import OfflineStore, TimestampFilter


class LocalOfflineStore(OfflineStore):
    """Append-only, Hive-partitioned Parquet offline store on the local filesystem."""

    def __init__(self, root: Path) -> None:
        self._offline_root = root / "feature_store" / "data" / "offline_store"

    def write(
        self,
        feature_group: str,
        data: pa.Table,
        *,
        event_timestamp_column: str,
        source_prefix: str,
    ) -> list[str]:
        """Append data to the offline store, partitioned by (year, month).

        Groups rows by the year and month of each row's event timestamp value,
        then writes one Parquet file per partition using a temp-then-replace
        atomic install. Returns the absolute paths of all files written.

        Args:
            feature_group: Registry name of the target group.
            data: PyArrow Table with the declared columns; must contain the
                event timestamp column typed as pa.timestamp('us').
            event_timestamp_column: Column name of the event timestamp field.
            source_prefix: File name prefix (e.g. 'ing').

        Returns:
            Sorted list of absolute file paths written (one per partition).

        Raises:
            OfflineStoreWriteError: Physical write failure. Per-file atomicity
                ensures no partial file is visible. Files for partitions written
                before the failure remain on disk (append-only, no rollback).
        """
        ts_col: pa.ChunkedArray = data.column(event_timestamp_column)
        ts_array = ts_col.combine_chunks() if isinstance(ts_col, pa.ChunkedArray) else ts_col

        # Derive (year, month) for every row from the event timestamp column.
        # The column is stored as timestamp('us') without timezone (UTC semantics).
        years = ts_array.cast(pa.timestamp("us")).cast(pa.int64())
        # Convert to Python datetime to extract year/month — safe at MVP scale.
        timestamps = ts_array.to_pylist()
        partition_indices: dict[tuple[int, int], list[int]] = {}
        for i, val in enumerate(timestamps):
            if val is None:
                continue
            if isinstance(val, datetime):
                y, m = int(val.year), int(val.month)
            else:
                # pyarrow may return a Timestamp wrapper; convert via isoformat
                import pandas as pd

                dt = pd.Timestamp(val).to_pydatetime()
                y, m = int(dt.year), int(dt.month)
            key = (y, m)
            partition_indices.setdefault(key, []).append(i)

        del years  # not used further

        write_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        written: list[str] = []

        for (year, month), row_indices in sorted(partition_indices.items()):
            partition_dir = self._offline_root / feature_group / f"year={year}" / f"month={month:02d}"
            try:
                partition_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise OfflineStoreWriteError(
                    format_actionable(
                        group=feature_group,
                        problem=f"could not create partition directory {partition_dir}: {exc}",
                        next_step="check filesystem permissions for the offline store root",
                    )
                ) from exc

            short_id = uuid4().hex[:6]
            final_name = f"{source_prefix}_{write_ts}_{short_id}.parquet"
            final_path = partition_dir / final_name

            partition_table = data.take(row_indices)

            fd, tmp_name = tempfile.mkstemp(dir=partition_dir, prefix=".tmp_", suffix=".parquet")
            tmp_path = Path(tmp_name)
            try:
                with os.fdopen(fd, "wb") as f:
                    pq.write_table(partition_table, f)
                os.replace(tmp_path, final_path)
            except BaseException as exc:
                tmp_path.unlink(missing_ok=True)
                raise OfflineStoreWriteError(
                    format_actionable(
                        group=feature_group,
                        problem=f"failed to write Parquet file {final_path}: {exc}",
                        next_step="check available disk space and filesystem permissions",
                    )
                ) from exc

            written.append(str(final_path.resolve()))

        return written

    def read(
        self,
        feature_group: str,
        *,
        event_timestamp_column: str,
        schema: pa.Schema,
        timestamp_filter: TimestampFilter | None = None,
    ) -> pa.Table:
        """Not yet implemented — lands in the historical retrieval feature."""
        raise NotImplementedError(
            "LocalOfflineStore.read() is not implemented in Feature 7. Historical retrieval lands in a later feature."
        )


__all__ = ["LocalOfflineStore"]
