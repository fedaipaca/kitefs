"""Online Store Manager (BB-07) — storage-agnostic coordination for materialization.

This module is free of any storage-backend imports. It receives data already
read by the offline store and prepares it for the provider's online write.
"""

from __future__ import annotations

import pyarrow as pa


def select_latest_rows(
    table: pa.Table,
    *,
    entity_key_column: str,
    event_timestamp_column: str,
) -> pa.Table:
    """Return exactly one row per entity key value, choosing the row with the
    maximum event timestamp. When two rows share the same entity key and the same
    event timestamp, the later-ingested row wins (determined by input row order,
    i.e., the row that appears later in *table* is preferred).

    The returned table has the same schema and column order as the input.
    Returns a schema-conforming empty table when *table* has no rows.
    """
    if len(table) == 0:
        return table

    # Add a stable row-order index so ties can be broken by position.
    n = len(table)
    row_order = pa.chunked_array([pa.array(range(n), type=pa.int64())])
    augmented = table.append_column("_kitefs_row_order", row_order)

    # Aggregate: for each entity key, find the max event timestamp.
    # Then, for rows that match (entity_key, max_ts), pick the one with the
    # largest row-order index (i.e., latest ingest position).
    entity_col = augmented.column(entity_key_column)
    ts_col = augmented.column(event_timestamp_column)
    order_col = augmented.column("_kitefs_row_order")

    # Build a dict: entity_key -> (max_ts, max_order, row_index)
    # We iterate once; this is acceptable for materialization batch sizes.
    best: dict = {}  # entity_key_value -> (max_ts, max_order, row_index)

    for i in range(n):
        ek = entity_col[i].as_py()
        ts = ts_col[i].as_py()
        ro = order_col[i].as_py()
        if ek not in best:
            best[ek] = (ts, ro, i)
        else:
            prev_ts, prev_ro, _ = best[ek]
            if ts > prev_ts or (ts == prev_ts and ro > prev_ro):
                best[ek] = (ts, ro, i)

    # Collect winning row indices in entity-insertion order for determinism.
    winning_indices = pa.array([row_idx for _, _, row_idx in best.values()], type=pa.int64())
    result = table.take(winning_indices)
    return result


__all__ = ["select_latest_rows"]
