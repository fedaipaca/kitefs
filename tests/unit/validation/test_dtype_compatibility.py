"""Unit tests for feature-column dtype compatibility checks."""

from __future__ import annotations

import pandas as pd
import pytest

from kitefs.enums import FeatureType, ValidationMode
from kitefs.errors import ValidationError
from kitefs.sdk.results import FeatureGroupDescription, FieldSpec
from kitefs.validation import validate_dataframe
from tests.unit.validation.conftest import make_description


def _desc_with_feature(name: str, dtype: FeatureType, *, expect: list | None = None) -> FeatureGroupDescription:
    """Return a description with a single feature of the given dtype."""
    return make_description(features=[FieldSpec(name=name, dtype=dtype, description=None, expect=expect)])


def _frame_with(feature_name: str, values: list) -> pd.DataFrame:
    """Build a minimal frame with entity key, timestamp, and one feature column."""
    return pd.DataFrame(
        {
            "id": list(range(len(values))),
            "ts": pd.to_datetime(["2024-01-01"] * len(values)),
            feature_name: values,
        }
    )


class TestIntegerDtype:
    """INTEGER FeatureType requires an integer-typed column."""

    def test_int64_column_accepted(self) -> None:
        """An int64 column satisfies the INTEGER dtype declaration."""
        desc = _desc_with_feature("feat", FeatureType.INTEGER)
        frame = _frame_with("feat", [1, 2, 3])
        assert frame["feat"].dtype == "int64"

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None
        assert report.fail_count == 0

    def test_float64_column_rejected(self) -> None:
        """A float64 column does not satisfy the INTEGER declaration (exact kind match)."""
        desc = _desc_with_feature("feat", FeatureType.INTEGER)
        frame = _frame_with("feat", [1.0, 2.0, 3.0])
        assert frame["feat"].dtype == "float64"

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failures = exc_info.value.report.failures
        assert any(f.constraint == "dtype(INTEGER)" and f.field == "feat" for f in failures)

    def test_string_column_rejected(self) -> None:
        """A string/object column does not satisfy the INTEGER declaration."""
        desc = _desc_with_feature("feat", FeatureType.INTEGER)
        frame = _frame_with("feat", ["a", "b"])

        with pytest.raises(ValidationError):
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")


class TestFloatDtype:
    """FLOAT FeatureType requires a float-typed column."""

    def test_float64_column_accepted(self) -> None:
        """A float64 column satisfies the FLOAT dtype declaration."""
        desc = _desc_with_feature("feat", FeatureType.FLOAT)
        frame = _frame_with("feat", [1.5, 2.5])

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None
        assert report.fail_count == 0

    def test_int64_column_rejected(self) -> None:
        """An int64 column does not satisfy the FLOAT declaration (exact kind match)."""
        desc = _desc_with_feature("feat", FeatureType.FLOAT)
        frame = _frame_with("feat", [1, 2, 3])
        assert frame["feat"].dtype == "int64"

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failures = exc_info.value.report.failures
        assert any(f.constraint == "dtype(FLOAT)" and f.field == "feat" for f in failures)

    def test_string_column_rejected(self) -> None:
        """A string column does not satisfy the FLOAT declaration."""
        desc = _desc_with_feature("feat", FeatureType.FLOAT)
        frame = _frame_with("feat", ["x", "y"])

        with pytest.raises(ValidationError):
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")


class TestStringDtype:
    """STRING FeatureType requires an object or StringDtype column."""

    def test_object_column_accepted(self) -> None:
        """An object-dtype column satisfies the STRING declaration."""
        desc = _desc_with_feature("feat", FeatureType.STRING)
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "feat": pd.Series(["hello"], dtype=object),
            }
        )

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0

    def test_int64_column_rejected(self) -> None:
        """An integer column does not satisfy the STRING declaration."""
        desc = _desc_with_feature("feat", FeatureType.STRING)
        frame = _frame_with("feat", [1, 2])

        with pytest.raises(ValidationError):
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")


class TestDatetimeDtype:
    """DATETIME FeatureType requires a datetime64 or object-of-datetimes column."""

    def test_datetime64_column_accepted(self) -> None:
        """A datetime64 column satisfies the DATETIME declaration."""
        desc = _desc_with_feature("feat", FeatureType.DATETIME)
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "feat": pd.to_datetime(["2024-01-01"]),
            }
        )

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0

    def test_float_column_rejected(self) -> None:
        """A float column does not satisfy the DATETIME declaration."""
        desc = _desc_with_feature("feat", FeatureType.DATETIME)
        frame = _frame_with("feat", [1.0, 2.0])

        with pytest.raises(ValidationError):
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")


class TestFullyNullColumn:
    """A fully-null feature column skips the dtype check (owned by not_null expectations)."""

    def test_all_null_column_passes_dtype_check(self) -> None:
        """An all-NaN column (float64) does not trigger a dtype failure for INTEGER."""
        desc = _desc_with_feature("feat", FeatureType.INTEGER)
        frame = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "feat": [None, None],
            }
        )
        # pandas represents [None, None] as float64 by default
        assert frame["feat"].isna().all()

        # No dtype failure — fully null column skips dtype check
        try:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        except ValidationError as exc:
            dtype_failures = [f for f in exc.report.failures if "dtype" in f.constraint]
            assert not dtype_failures, f"Unexpected dtype failure on all-null column: {dtype_failures}"


class TestFilterModeDtype:
    """FILTER mode drops rows with dtype mismatches rather than raising."""

    def test_incompatible_row_dropped_compatible_row_kept(self) -> None:
        """In FILTER mode, a row whose feature value fails dtype check is dropped."""
        desc = _desc_with_feature("feat", FeatureType.INTEGER)
        # Mixed object column: row 0 is an int (passes), row 1 is a float (fails INTEGER)
        frame = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "feat": pd.Series([1, 1.5], dtype=object),
            }
        )

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")

        assert len(result_frame) == 1
        assert result_frame.iloc[0]["id"] == 1
        assert report is not None
        assert report.fail_count == 1
        assert report.pass_count == 1
        assert any(f.constraint == "dtype(INTEGER)" for f in report.failures)

    def test_all_incompatible_rows_produce_empty_frame(self) -> None:
        """When all rows fail dtype check in FILTER mode, an empty DataFrame is returned."""
        desc = _desc_with_feature("feat", FeatureType.FLOAT)
        frame = _frame_with("feat", ["x", "y"])  # object dtype strings for FLOAT

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")

        assert len(result_frame) == 0
        assert report is not None
        assert report.fail_count == 2
        assert report.pass_count == 0
