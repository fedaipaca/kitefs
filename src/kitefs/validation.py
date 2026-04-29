"""Validation engine — stateless schema and data validation for DataFrames.

Two-phase validation:
  Phase 1 (schema): column presence and null structural columns. Always ERROR semantics.
  Phase 2 (data): type conformance and feature expectations. Respects ValidationMode.

The engine has zero internal dependencies — it receives a FeatureGroup definition
and a DataFrame, and returns a ValidationReport (plus optionally a filtered DataFrame).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd
from pandas import DataFrame

from kitefs.definitions import (
    Expect,
    FeatureGroup,
    FeatureType,
    ValidationMode,
)
from kitefs.exceptions import DataValidationError, SchemaValidationError

# Type mapping: FeatureType → compatible Pandas dtype checker


def _is_integer_compatible(series: pd.Series) -> bool:  # type: ignore[type-arg]
    """Check if a Series holds integer-compatible data.

    Pandas promotes int64 to float64 when nulls are present, so a float64
    column where all non-null values are whole numbers is also acceptable.
    """
    if pd.api.types.is_integer_dtype(series):
        return True
    if pd.api.types.is_float_dtype(series):
        non_null = series.dropna()
        if non_null.empty:
            return True
        return bool((non_null == non_null.astype("int64")).all())
    return False


def _is_float_compatible(series: pd.Series) -> bool:  # type: ignore[type-arg]
    """Check if a Series holds float-compatible data (includes integers)."""
    return bool(pd.api.types.is_float_dtype(series) or pd.api.types.is_integer_dtype(series))


def _is_string_compatible(series: pd.Series) -> bool:  # type: ignore[type-arg]
    """Check if a Series holds string/object data."""
    return bool(pd.api.types.is_string_dtype(series))


def _is_datetime_compatible(series: pd.Series) -> bool:  # type: ignore[type-arg]
    """Check if a Series holds datetime64 data."""
    return bool(pd.api.types.is_datetime64_any_dtype(series))


_TypeChecker = Callable[[pd.Series], bool]

_TYPE_CHECKERS: dict[FeatureType, tuple[str, _TypeChecker]] = {
    FeatureType.STRING: ("string (object)", _is_string_compatible),
    FeatureType.INTEGER: ("int64", _is_integer_compatible),
    FeatureType.FLOAT: ("float64", _is_float_compatible),
    FeatureType.DATETIME: ("datetime64", _is_datetime_compatible),
}


# Report types


@dataclass(frozen=True)
class FailureDetail:
    """A single per-row validation failure."""

    entity_key_value: str | int | float | None
    field: str
    expected: str
    actual: str


@dataclass(frozen=True)
class ValidationReport:
    """Structured result of a validation run.

    Produced by both schema and data validation. In ERROR mode with failures,
    the report is embedded in the raised exception for programmatic access.
    """

    total_count: int
    passed_count: int
    failed_count: int
    failures: tuple[FailureDetail, ...]


# Expectation evaluators


def _eval_not_null(series: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    """Return a boolean mask where True means the value is not null."""
    return series.notna()


def _eval_gt(series: pd.Series, value: int | float) -> pd.Series:  # type: ignore[type-arg]
    """Return a boolean mask where True means value > threshold."""
    return series > value


def _eval_gte(series: pd.Series, value: int | float) -> pd.Series:  # type: ignore[type-arg]
    """Return a boolean mask where True means value >= threshold."""
    return series >= value


def _eval_lt(series: pd.Series, value: int | float) -> pd.Series:  # type: ignore[type-arg]
    """Return a boolean mask where True means value < threshold."""
    return series < value


def _eval_lte(series: pd.Series, value: int | float) -> pd.Series:  # type: ignore[type-arg]
    """Return a boolean mask where True means value <= threshold."""
    return series <= value


def _eval_one_of(series: pd.Series, values: tuple | list) -> pd.Series:  # type: ignore[type-arg]
    """Return a boolean mask where True means value is in the allowed set."""
    return series.isin(values)


_Evaluator = Callable[[pd.Series, dict[str, Any]], pd.Series]

_EVALUATORS: dict[str, _Evaluator] = {
    "not_null": lambda s, _: _eval_not_null(s),
    "gt": lambda s, c: _eval_gt(s, c["value"]),
    "gte": lambda s, c: _eval_gte(s, c["value"]),
    "lt": lambda s, c: _eval_lt(s, c["value"]),
    "lte": lambda s, c: _eval_lte(s, c["value"]),
    "one_of": lambda s, c: _eval_one_of(s, c["values"]),
}


# Phase 1 — Schema validation


def validate_schema(
    definition: FeatureGroup,
    df: DataFrame,
) -> tuple[ValidationReport, DataFrame]:
    """Validate DataFrame schema against a FeatureGroup definition (Phase 1).

    Checks column presence and null structural columns. Extra columns
    present in the DataFrame but absent from the definition are silently
    dropped from the returned DataFrame.

    Always uses ERROR semantics — raises on any schema issue regardless
    of the configured ValidationMode.

    Returns a (report, cleaned_df) tuple on success.
    Raises SchemaValidationError listing all issues on failure.
    """
    expected_columns = _expected_column_names(definition)
    df_columns = set(df.columns)

    errors: list[str] = []

    # --- Missing columns ---
    missing = expected_columns - df_columns
    if missing:
        sorted_missing = sorted(missing)
        errors.append(
            f"Missing required column(s): {', '.join(sorted_missing)}. "
            f"The DataFrame must contain all columns declared in the feature group definition."
        )

    # --- Null structural columns (only check if columns exist) ---
    entity_name = definition.entity_key.name
    ts_name = definition.event_timestamp.name

    if entity_name in df_columns:
        entity_series = cast(pd.Series, df[entity_name])  # type: ignore[type-arg]
        null_count = int(entity_series.isna().sum())
        if null_count > 0:
            errors.append(
                f"Entity key column '{entity_name}' contains {null_count} null value(s). "
                f"Entity keys must not be null — every record needs a valid identifier."
            )

    if ts_name in df_columns:
        ts_series = cast(pd.Series, df[ts_name])  # type: ignore[type-arg]
        null_count = int(ts_series.isna().sum())
        if null_count > 0:
            errors.append(
                f"Event timestamp column '{ts_name}' contains {null_count} null value(s). "
                f"Event timestamps must not be null — they are required for partitioning and joins."
            )

    if errors:
        total = len(df)
        failures = tuple(
            FailureDetail(entity_key_value=None, field="_schema", expected="valid schema", actual=e) for e in errors
        )
        report = ValidationReport(
            total_count=total,
            passed_count=0,
            failed_count=total,
            failures=failures,
        )
        raise SchemaValidationError(
            "Schema validation failed:\n" + "\n".join(f"  - {e}" for e in errors),
            report=report,
        )

    # Drop extra columns, keep only declared columns in definition order
    ordered_columns = [
        definition.entity_key.name,
        definition.event_timestamp.name,
        *[f.name for f in definition.features],
    ]
    cleaned_df: DataFrame = df[ordered_columns].copy()  # type: ignore[assignment]

    total = len(cleaned_df)
    report = ValidationReport(
        total_count=total,
        passed_count=total,
        failed_count=0,
        failures=(),
    )
    return report, cleaned_df


# Phase 2 — Data validation


def validate_data(
    definition: FeatureGroup,
    df: DataFrame,
    mode: ValidationMode,
) -> tuple[ValidationReport, DataFrame]:
    """Validate feature values against type declarations and expectations (Phase 2).

    Assumes the DataFrame has already passed schema validation (Phase 1).
    Behaviour depends on the mode:
      NONE  — skip all checks, return pass-all report and original df.
      ERROR — any failure raises DataValidationError with full report.
      FILTER — failing rows excluded, passing rows + report returned.
    """
    total = len(df)

    if mode == ValidationMode.NONE:
        report = ValidationReport(
            total_count=total,
            passed_count=total,
            failed_count=0,
            failures=(),
        )
        return report, df

    entity_key_name = definition.entity_key.name
    all_failures: list[FailureDetail] = []
    # Track which rows have at least one failure (for FILTER mode)
    row_failed = pd.Series(False, index=df.index)

    for feature in definition.features:
        col = feature.name
        series = cast(pd.Series, df[col])  # type: ignore[type-arg]

        # --- Type check ---
        expected_label, checker = _TYPE_CHECKERS[feature.dtype]
        if not checker(series):
            actual_dtype = str(series.dtype)
            row_failed[:] = True
            # Report a single column-level failure rather than N per-row entries
            all_failures.append(
                FailureDetail(
                    entity_key_value="*",
                    field=col,
                    expected=f"dtype {expected_label}",
                    actual=f"dtype {actual_dtype} (all {total} row(s) affected)",
                )
            )
            # Skip expectation checks — the entire column has wrong type
            continue

        # --- Expectation checks ---
        if feature.expect is not None:
            _check_expectations(
                df=df,
                series=series,
                col=col,
                expect=feature.expect,
                entity_key_name=entity_key_name,
                all_failures=all_failures,
                row_failed=row_failed,
            )

    failed_count = int(row_failed.sum())
    passed_count = total - failed_count
    report = ValidationReport(
        total_count=total,
        passed_count=passed_count,
        failed_count=failed_count,
        failures=tuple(all_failures),
    )

    if mode == ValidationMode.ERROR and failed_count > 0:
        raise DataValidationError(
            f"Data validation failed ({failed_count} of {total} record(s) invalid):\n" + _format_failures(all_failures),
            report=report,
        )

    if mode == ValidationMode.FILTER:
        filtered_df: DataFrame = df[~row_failed].reset_index(drop=True)  # type: ignore[assignment]
        return report, filtered_df

    # ERROR mode, no failures
    return report, df


# Private helpers


def _expected_column_names(definition: FeatureGroup) -> set[str]:
    """Derive the set of expected column names from a FeatureGroup definition."""
    return {
        definition.entity_key.name,
        definition.event_timestamp.name,
        *(f.name for f in definition.features),
    }


def _safe_entity_key(
    df: DataFrame,
    entity_key_name: str,
    idx: object,
) -> str | int | float | None:
    """Safely extract the entity key value for a given row index."""
    val = df.at[idx, entity_key_name]
    if pd.isna(val):
        return None
    return val  # type: ignore[no-any-return]


def _constraint_description(constraint: dict) -> str:
    """Human-readable description of a single constraint dict."""
    ctype = constraint["type"]
    if ctype == "not_null":
        return "not_null"
    if ctype == "one_of":
        return f"one_of({constraint['values']!r})"
    return f"{ctype}({constraint['value']})"


def _check_expectations(
    *,
    df: DataFrame,
    series: pd.Series,  # type: ignore[type-arg]
    col: str,
    expect: Expect,
    entity_key_name: str,
    all_failures: list[FailureDetail],
    row_failed: pd.Series,  # type: ignore[type-arg]
) -> None:
    """Evaluate all constraints on a feature column, collecting failures."""
    for constraint in expect.constraints:
        ctype = constraint["type"]
        evaluator = _EVALUATORS[ctype]
        mask = evaluator(series, constraint)

        # Null values produce NaN in comparisons; treat as failures
        failing = ~mask.fillna(False)
        if failing.any():
            row_failed |= failing
            expected_desc = _constraint_description(constraint)
            for idx in df.index[failing]:
                actual_val = series.loc[idx]
                all_failures.append(
                    FailureDetail(
                        entity_key_value=_safe_entity_key(df, entity_key_name, idx),
                        field=col,
                        expected=expected_desc,
                        actual=repr(actual_val),
                    )
                )


def _format_failures(failures: list[FailureDetail], max_shown: int = 20) -> str:
    """Format failure details for inclusion in error messages."""
    lines = []
    for f in failures[:max_shown]:
        lines.append(
            f"  - entity_key={f.entity_key_value!r}, field='{f.field}', expected={f.expected}, actual={f.actual}"
        )
    if len(failures) > max_shown:
        lines.append(f"  ... and {len(failures) - max_shown} more failure(s)")
    return "\n".join(lines)
