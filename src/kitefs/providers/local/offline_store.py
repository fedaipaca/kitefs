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
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from kitefs.errors import OfflineStoreReadError, OfflineStoreWriteError, format_actionable
from kitefs.providers.base import OfflineStore, TimestampFilter


def _build_filter_expr(
    timestamp_filter: TimestampFilter | None,
    event_timestamp_column: str,
) -> object:
    """Build a PyArrow dataset filter expression from a TimestampFilter.

    Combines row-level event-timestamp predicates with approximate year/month
    partition predicates so pyarrow can prune whole monthly partitions before
    opening any files.  All supplied bounds are AND-ed together.

    Datetime bounds are normalized to UTC-naive before comparison because the
    offline store writes timestamps as pa.timestamp('us') without timezone info
    (UTC semantics per CON-006).

    Returns None when no bounds are supplied.
    """
    if timestamp_filter is None:
        return None

    def _naive(dt: datetime) -> datetime:
        """Strip timezone; both naive (UTC) and UTC-aware are treated as UTC."""
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

    ts_col = pc.field(event_timestamp_column)
    year_col = pc.field("year")
    month_col = pc.field("month")

    parts: list[object] = []

    if timestamp_filter.gte is not None:
        val = _naive(timestamp_filter.gte)
        ts_scalar = pa.scalar(val, type=pa.timestamp("us"))
        y, m = val.year, val.month
        parts.append(ts_col >= ts_scalar)
        # Partition pruning: keep any year after y, or same year with month >= m
        parts.append((year_col > y) | ((year_col == y) & (month_col >= m)))

    if timestamp_filter.gt is not None:
        val = _naive(timestamp_filter.gt)
        ts_scalar = pa.scalar(val, type=pa.timestamp("us"))
        y, m = val.year, val.month
        parts.append(ts_col > ts_scalar)
        # Can't prune the boundary month for strict gt; same lower-bound pruning
        parts.append((year_col > y) | ((year_col == y) & (month_col >= m)))

    if timestamp_filter.lte is not None:
        val = _naive(timestamp_filter.lte)
        ts_scalar = pa.scalar(val, type=pa.timestamp("us"))
        y, m = val.year, val.month
        parts.append(ts_col <= ts_scalar)
        # Partition pruning: keep any year before y, or same year with month <= m
        parts.append((year_col < y) | ((year_col == y) & (month_col <= m)))

    if timestamp_filter.lt is not None:
        val = _naive(timestamp_filter.lt)
        ts_scalar = pa.scalar(val, type=pa.timestamp("us"))
        y, m = val.year, val.month
        parts.append(ts_col < ts_scalar)
        # Can't prune boundary month for strict lt; same upper-bound pruning
        parts.append((year_col < y) | ((year_col == y) & (month_col <= m)))

    if not parts:
        return None

    result = parts[0]
    for part in parts[1:]:
        result = result & part  # type: ignore[operator]
    return result


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
        """Read historical feature rows from the local offline store.

        When *timestamp_filter* is None, enumerates all Parquet files sorted by
        (st_mtime_ns, path) and concatenates them in that order. This preserves
        ingest order so that tie-breaking in select_latest_rows() correctly
        picks the later-ingested row when timestamps are equal.

        When *timestamp_filter* is provided, uses pyarrow.dataset with Hive
        partitioning to scan with row-level and partition-level predicates.

        Args:
            feature_group: Registry name of the feature group to read.
            event_timestamp_column: Column name of the event timestamp field.
            schema: Expected PyArrow schema; defines the output columns and is
                used to construct the empty return value when no data is found.
            timestamp_filter: Optional bounds for the event timestamp. All
                supplied bounds (gt, gte, lt, lte) are combined with AND.

        Returns:
            A PyArrow Table with columns matching schema.names, filtered to rows
            satisfying the timestamp bounds. Returns an empty table with the
            provided schema when no data exists or no rows match.

        Raises:
            OfflineStoreReadError: Any filesystem or Parquet read failure.
        """
        group_dir = self._offline_root / feature_group
        if not group_dir.exists() or not any(group_dir.rglob("*.parquet")):
            return schema.empty_table()

        if timestamp_filter is None:
            # Full read for materialization: enumerate files in ingest order so
            # the later-ingested row wins ties in select_latest_rows().
            parquet_files = sorted(
                group_dir.rglob("*.parquet"),
                key=lambda p: (p.stat().st_mtime_ns, str(p)),
            )
            if not parquet_files:
                return schema.empty_table()
            try:
                tables = [pq.read_table(str(p), columns=schema.names) for p in parquet_files]
            except Exception as exc:
                raise OfflineStoreReadError(
                    format_actionable(
                        group=feature_group,
                        problem=f"failed to read Parquet file from offline store: {exc}",
                        next_step="check that Parquet files are not corrupted and have the expected columns",
                    )
                ) from exc
            return pa.concat_tables(tables)

        try:
            dataset = ds.dataset(str(group_dir), format="parquet", partitioning="hive")
        except Exception as exc:
            raise OfflineStoreReadError(
                format_actionable(
                    group=feature_group,
                    problem=f"failed to open offline store dataset at {group_dir}: {exc}",
                    next_step="check that the offline store directory and files are readable",
                )
            ) from exc

        filter_expr = _build_filter_expr(timestamp_filter, event_timestamp_column)

        try:
            table = dataset.to_table(columns=schema.names, filter=filter_expr)
        except Exception as exc:
            raise OfflineStoreReadError(
                format_actionable(
                    group=feature_group,
                    problem=f"failed to read offline store data: {exc}",
                    next_step="check that Parquet files are not corrupted and have the expected columns",
                )
            ) from exc

        return table


__all__ = ["LocalOfflineStore"]
