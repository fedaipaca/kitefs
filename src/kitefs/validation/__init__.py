"""Stateless DataFrame validation engine.

Validates a pandas DataFrame against a registered feature group's schema and
expectations. Does not perform any storage I/O; callers decide when to invoke
it and which ValidationMode to use.

Public interface:
    validate_dataframe(description, frame, mode, *, operation)
        -> tuple[DataFrame, ValidationReport | None]
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd

from kitefs.enums import FeatureType, ValidationMode
from kitefs.errors import IngestionShapeError, ValidationError, format_actionable
from kitefs.registry.serializer import _DATETIME_FMT
from kitefs.sdk.results import (
    FeatureGroupDescription,
    ValidationFailure,
    ValidationReport,
)

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate_dataframe(
    description: FeatureGroupDescription,
    frame: pd.DataFrame,
    mode: ValidationMode,
    *,
    operation: str,
) -> tuple[pd.DataFrame, ValidationReport | None]:
    """Validate a DataFrame against the registered feature group's schema and expectations.

    Structural checks (entity key, event timestamp, join key: not-null, dtype, UTC)
    always run regardless of mode and raise ValidationError immediately on any failure.

    In NONE mode, feature-level checks are skipped and (frame, None) is returned.
    In ERROR mode, any feature failure raises ValidationError carrying a ValidationReport.
    In FILTER mode, failing rows are dropped and the passing subset plus a
    ValidationReport are returned. Column-level feature faults (wrong column dtype,
    non-UTC tz-aware datetime64 column) cannot be fixed by dropping rows and raise
    ValidationError even in FILTER mode.

    Args:
        description: The registered feature group description from the registry.
        frame: The pandas DataFrame to validate.
        mode: ERROR, FILTER, or NONE.
        operation: Context label for actionable error messages (e.g. "ingestion").

    Returns:
        A (frame, report) tuple. In NONE mode, report is None.
        In ERROR mode on success, report has pass_count=len(frame) and fail_count=0.
        In FILTER mode, frame is the passing row subset and report reflects dropped rows.

    Raises:
        IngestionShapeError: A required structural or feature column is missing.
        ValidationError: Any structural failure (in any mode), any feature failure in
            ERROR mode, or a non-row-filterable feature failure in FILTER mode.
    """
    _check_shape(description, frame)

    structural = _structural_failures(description, frame)
    if structural:
        n = len(structural)
        raise ValidationError(
            format_actionable(
                setting=operation,
                group=description.name,
                problem=f"structural validation failed with {n} failure(s)",
                next_step="fix null values, dtype mismatches, or non-UTC datetimes in the structural columns",
            ),
            report=ValidationReport(pass_count=0, fail_count=len(frame), failures=structural),
        )

    if mode is ValidationMode.NONE:
        return frame, None

    feature, fatal = _feature_failures(description, frame)
    if fatal:
        n = len(feature)
        raise ValidationError(
            format_actionable(
                setting=operation,
                group=description.name,
                problem=f"feature validation failed with {n} column-level failure(s)",
                next_step="fix column dtype mismatches or non-UTC tz-aware datetimes in the feature columns",
            ),
            report=ValidationReport(pass_count=0, fail_count=len(frame), failures=feature),
        )

    if mode is ValidationMode.ERROR:
        if feature:
            fail_rows = {f.row_index for f in feature}
            raise ValidationError(
                format_actionable(
                    setting=operation,
                    group=description.name,
                    problem=f"feature validation failed with {len(feature)} failure(s) across {len(fail_rows)} row(s)",
                    next_step="fix or remove the failing rows before ingesting",
                ),
                report=ValidationReport(
                    pass_count=len(frame) - len(fail_rows),
                    fail_count=len(fail_rows),
                    failures=feature,
                ),
            )
        return frame, ValidationReport(pass_count=len(frame), fail_count=0, failures=[])

    # FILTER mode: drop failing rows, return the passing subset.
    drop_positions = {f.row_index for f in feature if f.row_index is not None}
    keep_positions = [i for i in range(len(frame)) if i not in drop_positions]
    filtered = frame.iloc[keep_positions]
    return (
        filtered,
        ValidationReport(
            pass_count=len(keep_positions),
            fail_count=len(drop_positions),
            failures=feature,
        ),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_shape(description: FeatureGroupDescription, frame: pd.DataFrame) -> None:
    """Raise IngestionShapeError if any required column is missing from the DataFrame.

    Extra columns are silently ignored — callers may pass wider DataFrames.
    """
    required = (
        {description.entity_key.name, description.event_timestamp.name}
        | {jk.name for jk in description.join_keys}
        | {f.name for f in description.features}
    )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise IngestionShapeError(
            format_actionable(
                group=description.name,
                problem=f"required columns missing: {missing}",
                next_step="add the missing columns to the DataFrame before validating",
            )
        )


def _col(frame: pd.DataFrame, name: str) -> pd.Series:
    """Return a column from a DataFrame as a typed Series.

    Pandas' __getitem__ stubs return Series | DataFrame; this narrows to Series
    so callers don't need per-call type ignores.
    """
    return frame[name]  # type: ignore[return-value]


def _py_scalar(val: Any) -> Any:
    """Convert numpy/pandas scalars to Python primitives; NA and NaN become None.

    Handles:
    - numpy scalars (int64, float64, …): converted via .item()
    - pandas NA (pd.NA): returned as None
    - float NaN: returned as None
    """
    if val is pd.NA:
        return None
    try:
        result = val.item()
        # IEEE 754: NaN != NaN — convert to None for clean failure reporting.
        return None if result != result else result
    except (AttributeError, ValueError):
        return val


def _ek_value(entity_key_series: pd.Series, pos: int) -> Any:
    """Return the entity key value at positional index pos as a Python scalar."""
    return _py_scalar(entity_key_series.iloc[pos])


def _is_dtype_compatible(series: pd.Series, dtype: FeatureType) -> bool:
    """Return True if the column's pandas dtype is compatible with the declared FeatureType.

    A fully-null column always passes — nullability is enforced by not_null expectations,
    not by dtype. This avoids false dtype failures on all-NaN columns (which pandas
    typically represents as float64).

    Dtype matching is exact-kind: INTEGER requires an integer dtype, FLOAT requires a
    float dtype. No cross-kind widening is accepted.
    """
    if series.isna().all():
        return True
    if dtype == FeatureType.INTEGER:
        return pd.api.types.is_integer_dtype(series)
    if dtype == FeatureType.FLOAT:
        return pd.api.types.is_float_dtype(series)
    if dtype == FeatureType.STRING:
        # Accept both object dtype (traditional) and pandas StringDtype (nullable string).
        return series.dtype == object or isinstance(series.dtype, pd.StringDtype)
    if dtype == FeatureType.DATETIME:
        if pd.api.types.is_datetime64_any_dtype(series):
            return True
        # Also accept an object column whose non-null values are all Python datetimes.
        if series.dtype == object:
            non_null = series.dropna()
            return non_null.empty or all(isinstance(v, datetime.datetime) for v in non_null)
        return False
    return False  # unreachable: FeatureType has exactly 4 members


def _null_failures(
    series: pd.Series,
    field_name: str,
    entity_key_series: pd.Series,
) -> list[ValidationFailure]:
    """Return one ValidationFailure per null value in series (structural not-null check)."""
    return [
        ValidationFailure(
            field=field_name,
            constraint="not_null",
            actual_value=None,
            entity_key_value=_ek_value(entity_key_series, pos),
            row_index=pos,
        )
        for pos, is_null in enumerate(series.isna())
        if is_null
    ]


def _utc_failures(
    series: pd.Series,
    field_name: str,
    entity_key_series: pd.Series,
) -> list[ValidationFailure]:
    """Return failures for non-UTC tz-aware datetime values.

    Rules:
    - Naive datetime64 or object datetimes → treated as UTC → no failure.
    - UTC-aware (offset 0) → no failure.
    - Non-UTC tz-aware datetime64 column → one column-level failure (row_index=None).
    - Non-UTC tz-aware Python datetime in an object column → per-row failure.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        # Naive numpy datetime64 has no .tz attribute; DatetimeTZDtype does.
        tz = getattr(series.dtype, "tz", None)
        if tz is None or str(tz) == "UTC":
            return []
        # Non-UTC tz on a datetime64 column is a column-level fault.
        return [
            ValidationFailure(
                field=field_name,
                constraint="utc",
                actual_value=str(tz),
                entity_key_value=None,
                row_index=None,
            )
        ]

    if series.dtype == object:
        # Object column: check each Python datetime value independently per-row.
        failures: list[ValidationFailure] = []
        for pos, val in enumerate(series):
            if not isinstance(val, datetime.datetime):
                continue
            if val.tzinfo is None:
                continue  # naive → treated as UTC
            offset = val.utcoffset()
            if offset is not None and offset.total_seconds() == 0:
                continue  # UTC offset 0 → pass
            failures.append(
                ValidationFailure(
                    field=field_name,
                    constraint="utc",
                    actual_value=str(val.tzinfo),
                    entity_key_value=_ek_value(entity_key_series, pos),
                    row_index=pos,
                )
            )
        return failures

    return []


def _check_field(
    name: str,
    dtype: FeatureType,
    series: pd.Series,
    entity_key_series: pd.Series,
    failures: list[ValidationFailure],
) -> None:
    """Append null, dtype, and UTC failures for a structural field in-place."""
    failures.extend(_null_failures(series, name, entity_key_series))
    if not _is_dtype_compatible(series, dtype):
        failures.append(
            ValidationFailure(
                field=name,
                constraint=f"dtype({dtype.value})",
                actual_value=str(series.dtype),
                entity_key_value=None,
                row_index=None,
            )
        )
    if dtype == FeatureType.DATETIME:
        failures.extend(_utc_failures(series, name, entity_key_series))


def _structural_failures(
    description: FeatureGroupDescription,
    frame: pd.DataFrame,
) -> list[ValidationFailure]:
    """Run null, dtype, and UTC checks for all structural columns.

    Structural columns are: entity key, event timestamp, and any declared join keys.
    """
    failures: list[ValidationFailure] = []
    ek_series = _col(frame, description.entity_key.name)
    _check_field(
        description.entity_key.name,
        description.entity_key.dtype,
        ek_series,
        ek_series,
        failures,
    )
    _check_field(
        description.event_timestamp.name,
        description.event_timestamp.dtype,
        _col(frame, description.event_timestamp.name),
        ek_series,
        failures,
    )
    for jk in description.join_keys:
        _check_field(jk.name, jk.dtype, _col(frame, jk.name), ek_series, failures)
    return failures


def _evaluate_expectation(
    series: pd.Series,
    constraint: dict[str, Any],
    field_name: str,
    entity_key_series: pd.Series,
) -> list[ValidationFailure]:
    """Evaluate one expectation constraint dict against a feature series.

    Returns one ValidationFailure per failing non-null row.
    Null values are skipped for comparison operators — not_null owns null detection.

    Constraint dict format (from the registry serializer):
        {"type": "not_null"}
        {"type": "gt"|"gte"|"lt"|"lte", "value": <int|float|ISO datetime string>}
        {"type": "is_in", "value": [<values...>]}

    Constraint string format in failures: "not_null", "gt(0)", "gte(0)",
    "lt(100)", "lte(100)", "is_in([...])" — matching the spec examples.
    """
    op = constraint["type"]

    if op == "not_null":
        return [
            ValidationFailure(
                field=field_name,
                constraint="not_null",
                actual_value=None,
                entity_key_value=_ek_value(entity_key_series, pos),
                row_index=pos,
            )
            for pos, is_null in enumerate(series.isna())
            if is_null
        ]

    if op in ("gt", "gte", "lt", "lte"):
        raw_value = constraint["value"]
        if isinstance(raw_value, str):
            raw_value = datetime.datetime.strptime(raw_value, _DATETIME_FMT).replace(tzinfo=datetime.UTC)
        threshold = raw_value
        # For naive datetime64 Series, strip tz from a UTC threshold to avoid the
        # tz-naive/tz-aware comparison error — naive is treated as UTC.
        if (
            pd.api.types.is_datetime64_any_dtype(series)
            and getattr(series.dtype, "tz", None) is None
            and isinstance(threshold, datetime.datetime)
            and threshold.tzinfo is not None
        ):
            threshold = threshold.replace(tzinfo=None)
        constraint_str = f"{op}({raw_value})"

        not_null = series.notna()
        if op == "gt":
            fail_mask = not_null & ~(series > threshold)
        elif op == "gte":
            fail_mask = not_null & ~(series >= threshold)
        elif op == "lt":
            fail_mask = not_null & ~(series < threshold)
        else:  # lte
            fail_mask = not_null & ~(series <= threshold)

        return [
            ValidationFailure(
                field=field_name,
                constraint=constraint_str,
                actual_value=_py_scalar(series.iloc[pos]),
                entity_key_value=_ek_value(entity_key_series, pos),
                row_index=pos,
            )
            for pos, is_fail in enumerate(fail_mask)
            if is_fail
        ]

    if op == "is_in":
        raw_list = constraint["value"]
        # Parse datetime strings if the column holds datetime values.
        parsed_list: list[Any] = [
            datetime.datetime.strptime(v, _DATETIME_FMT).replace(tzinfo=datetime.UTC)
            if isinstance(v, str) and pd.api.types.is_datetime64_any_dtype(series)
            else v
            for v in raw_list
        ]
        # For naive datetime64 Series, strip tz from UTC thresholds.
        if pd.api.types.is_datetime64_any_dtype(series) and getattr(series.dtype, "tz", None) is None:
            parsed_list = [
                v.replace(tzinfo=None) if isinstance(v, datetime.datetime) and v.tzinfo is not None else v
                for v in parsed_list
            ]
        constraint_str = f"is_in({parsed_list})"
        not_null = series.notna()
        fail_mask = not_null & ~series.isin(parsed_list)
        return [
            ValidationFailure(
                field=field_name,
                constraint=constraint_str,
                actual_value=_py_scalar(series.iloc[pos]),
                entity_key_value=_ek_value(entity_key_series, pos),
                row_index=pos,
            )
            for pos, is_fail in enumerate(fail_mask)
            if is_fail
        ]

    return []  # unknown operator type — skip silently


def _feature_failures(
    description: FeatureGroupDescription,
    frame: pd.DataFrame,
) -> tuple[list[ValidationFailure], bool]:
    """Check feature dtype, UTC, and expectation constraints.

    Returns (failures, fatal) where fatal=True means a column-level failure was
    encountered that cannot be fixed by dropping rows (wrong column dtype or a
    non-UTC tz-aware datetime64 column). Callers raise ValidationError on fatal
    instead of attempting row-level filtering.

    Features are processed in declared order (alphabetical in FeatureGroupDescription,
    per the serializer). Constraints are evaluated in the order they appear in the
    serialized expect list. Per-row failures within a constraint are in ascending
    positional order.
    """
    failures: list[ValidationFailure] = []
    fatal = False
    ek_series = _col(frame, description.entity_key.name)

    for feature in description.features:
        series = _col(frame, feature.name)

        # Column dtype check: column-level failure → fatal (not row-filterable).
        if not _is_dtype_compatible(series, feature.dtype):
            failures.append(
                ValidationFailure(
                    field=feature.name,
                    constraint=f"dtype({feature.dtype.value})",
                    actual_value=str(series.dtype),
                    entity_key_value=None,
                    row_index=None,
                )
            )
            fatal = True
            continue  # skip expectations — values may not be comparable with wrong dtype

        # UTC check for DATETIME features.
        if feature.dtype == FeatureType.DATETIME:
            utc_fails = _utc_failures(series, feature.name, ek_series)
            if utc_fails:
                # datetime64 with non-UTC tz is a column-level failure → fatal.
                if any(f.row_index is None for f in utc_fails):
                    fatal = True
                failures.extend(utc_fails)
                if fatal:
                    continue  # skip expectations — column timezone is wrong

        # Expectation constraints (per-row).
        if feature.expect is not None:
            for c in feature.expect:
                failures.extend(_evaluate_expectation(series, c, feature.name, ek_series))

    return failures, fatal


__all__ = ["validate_dataframe"]
