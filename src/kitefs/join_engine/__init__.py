"""Stateless point-in-time join engine for historical retrieval."""

from __future__ import annotations

from typing import Any

import pandas as pd


def point_in_time_join(
    *,
    base_frame: pd.DataFrame,
    joined_frame: pd.DataFrame,
    base_join_key_column: str,
    base_event_timestamp_column: str,
    joined_entity_key_column: str,
    joined_event_timestamp_column: str,
    joined_output_columns: list[str],
    joined_group_name: str,
) -> pd.DataFrame:
    """Attach the latest eligible joined row to each base row.

    The join is left-sided: every base row remains in the output. For each base
    row, the selected joined row must have the same entity value and a joined
    event timestamp at or before the base event timestamp. Equal joined
    timestamps are resolved by joined DataFrame row order, with later rows
    winning; providers can therefore expose ingestion-order semantics by
    returning rows in ingestion order.
    """
    base = base_frame.reset_index(drop=True).copy()
    joined = joined_frame.reset_index(drop=True).copy()

    prefixed_columns = [f"{joined_group_name}_{column}" for column in joined_output_columns]
    if len(base) == 0:
        return pd.concat([base, pd.DataFrame(columns=prefixed_columns)], axis=1)

    matched_rows: list[dict[str, Any]] = []
    for _, base_row in base.iterrows():
        candidates = joined[
            (joined[joined_entity_key_column] == base_row[base_join_key_column])
            & (joined[joined_event_timestamp_column] <= base_row[base_event_timestamp_column])
        ]

        if len(candidates) == 0:
            matched_rows.append({column: pd.NA for column in prefixed_columns})
            continue

        candidates = candidates.assign(_kitefs_join_order=candidates.index)
        winner = candidates.sort_values([joined_event_timestamp_column, "_kitefs_join_order"], kind="mergesort").iloc[
            -1
        ]
        matched_rows.append(
            {prefixed: winner[column] for column, prefixed in zip(joined_output_columns, prefixed_columns, strict=True)}
        )

    joined_result = pd.DataFrame(matched_rows, columns=prefixed_columns)
    return pd.concat([base, joined_result], axis=1)


__all__ = ["point_in_time_join"]
