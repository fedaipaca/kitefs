"""Offline store coordination — storage-agnostic ingestion helpers.

This module holds logic that is shared by all offline store implementations.
It has no dependency on any specific storage backend; all I/O goes through
the OfflineStore ABC.

Public interface:
    prepare_ingestion_table(description, frame) -> pyarrow.Table
        Build a PyArrow Table from a validated DataFrame, keeping only the
        declared columns (entity key, event timestamp, join keys, features) in
        stable registry order and applying the required type mapping.
"""

from __future__ import annotations

import datetime

import pandas as pd
import pyarrow as pa

from kitefs.enums import FeatureType
from kitefs.sdk.results import FeatureGroupDescription

# Mapping from FeatureType to the PyArrow storage type used in offline Parquet files.
# Per docs/specs/05-data-and-storage-contracts.md § Type Mapping.
_FEATURE_TYPE_TO_PA: dict[FeatureType, pa.DataType] = {
    FeatureType.STRING: pa.string(),
    FeatureType.INTEGER: pa.int64(),
    FeatureType.FLOAT: pa.float64(),
    FeatureType.DATETIME: pa.timestamp("us"),  # naive microsecond, UTC semantics
}


def prepare_ingestion_table(
    description: FeatureGroupDescription,
    frame: pd.DataFrame,
) -> pa.Table:
    """Build a typed PyArrow Table from a validated DataFrame for offline ingestion.

    Keeps only declared columns in stable registry order:
        entity key → event timestamp → join keys (alphabetical) → features (alphabetical).

    Drops any extra columns the caller may have passed. DATETIME columns are
    converted to UTC microsecond precision before casting so that PyArrow can
    safely store them as timestamp('us') without timezone information (matching
    the offline Parquet schema in the storage contracts).

    Args:
        description: The registered feature group description from the registry.
        frame: A validated pandas DataFrame. All required columns are present.

    Returns:
        A PyArrow Table with exactly the declared columns, ordered as above,
        typed per the storage contracts.
    """
    # Build the ordered list of (column_name, FeatureType) pairs.
    ordered_cols: list[tuple[str, FeatureType]] = [
        (description.entity_key.name, description.entity_key.dtype),
        (description.event_timestamp.name, description.event_timestamp.dtype),
    ]
    for jk in description.join_keys:
        ordered_cols.append((jk.name, jk.dtype))
    for feat in description.features:
        ordered_cols.append((feat.name, feat.dtype))

    # Select and convert columns.
    arrays: list[pa.Array] = []
    fields: list[pa.Field] = []

    for col_name, col_type in ordered_cols:
        series = frame[col_name]
        pa_type = _FEATURE_TYPE_TO_PA[col_type]

        if col_type == FeatureType.DATETIME:
            series = _to_utc_microsecond(pd.Series(series))

        arrays.append(pa.array(series, type=pa_type))
        fields.append(pa.field(col_name, pa_type))

    return pa.table(
        {col_name: arr for col_name, arr in zip([c for c, _ in ordered_cols], arrays, strict=True)},
        schema=pa.schema(fields),
    )


def _to_utc_microsecond(series: pd.Series) -> pd.Series:
    """Normalize a datetime Series to UTC-naive microsecond precision.

    Rules (per CON-006 and the storage contracts):
    - Naive datetime64 values are treated as UTC; no conversion needed.
    - UTC-aware values have their timezone stripped (they are already UTC).

    The result is always a pandas datetime64[us] Series without timezone,
    suitable for casting to pa.timestamp('us').
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        tz = getattr(series.dtype, "tz", None)
        if tz is not None:
            # UTC-aware: strip timezone to produce naive microsecond values.
            series = series.dt.tz_localize(None)
        # Ensure microsecond precision (pandas may default to ns).
        return series.astype("datetime64[us]")

    # Object column with Python datetimes (naive or UTC-aware).
    def _normalize(val: object) -> object:
        if val is None or val is pd.NaT:
            return None
        if isinstance(val, datetime.datetime):
            if val.tzinfo is not None:
                # Already validated as UTC by the validation engine; strip tz.
                val = val.replace(tzinfo=None)
            return val
        return val

    normalized = series.map(_normalize)
    return pd.to_datetime(normalized, utc=False).astype("datetime64[us]")


__all__ = ["prepare_ingestion_table"]
