"""Tests for validate_data (Phase 2 — data validation)."""

import pandas as pd
import pytest
from helpers import make_feature_group

from kitefs.definitions import (
    Expect,
    Feature,
    FeatureType,
    ValidationMode,
)
from kitefs.exceptions import DataValidationError
from kitefs.validation import validate_data


def _group_with_features(*features: Feature) -> "FeatureGroup":  # type: ignore[name-defined]  # noqa: F821
    """Build a FeatureGroup with the given features (plus structural columns)."""
    return make_feature_group(features=list(features))


def _base_df(**col_overrides: object) -> pd.DataFrame:
    """Build a DataFrame with structural columns and optional feature overrides."""
    data: dict = {
        "id": col_overrides.pop("id", [1, 2, 3]),  # type: ignore[union-attr]
        "ts": col_overrides.pop("ts", pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])),  # type: ignore[union-attr]
    }
    data.update(col_overrides)  # type: ignore[arg-type]
    return pd.DataFrame(data)


class TestNoneMode:
    """NONE mode skips Phase 2 entirely."""

    def test_none_mode_skips_all_checks(self) -> None:
        """NONE mode returns a pass-all report and the original DataFrame."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)))
        # Deliberately bad data — nulls and negatives
        df = _base_df(value=[None, -5.0, 0.0])

        report, result_df = validate_data(group, df, ValidationMode.NONE)

        assert report.total_count == 3
        assert report.passed_count == 3
        assert report.failed_count == 0
        assert report.failures == ()
        assert len(result_df) == 3  # unfiltered


class TestTypeChecks:
    """Phase 2 detects column dtype mismatches."""

    def test_string_in_integer_column(self) -> None:
        """Object dtype column flagged when INTEGER expected."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER))
        df = _base_df(value=["a", "b", "c"])  # object dtype

        with pytest.raises(DataValidationError, match="dtype int64"):
            validate_data(group, df, ValidationMode.ERROR)

    def test_integer_column_with_nulls_promoted_to_float(self) -> None:
        """Integer column with nulls (promoted to float64 by Pandas) is accepted."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER))
        # Pandas promotes int to float64 when there are nulls
        df = _base_df(value=[1.0, None, 3.0])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        # Should pass type check — float64 with whole numbers is integer-compatible
        assert report.failed_count == 0

    def test_float_dtype_for_integer_fails_when_non_whole(self) -> None:
        """Float column with fractional values fails INTEGER type check."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER))
        df = _base_df(value=[1.5, 2.7, 3.3])

        with pytest.raises(DataValidationError, match="dtype int64"):
            validate_data(group, df, ValidationMode.ERROR)

    def test_float_accepts_integers(self) -> None:
        """Integer column is accepted for FLOAT dtype (widening is fine)."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT))
        df = _base_df(value=[1, 2, 3])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0

    def test_string_dtype_check(self) -> None:
        """Object dtype is accepted for STRING."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.STRING))
        df = _base_df(value=["a", "b", "c"])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0

    def test_datetime_dtype_check(self) -> None:
        """Datetime64 dtype is accepted for DATETIME."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.DATETIME))
        df = _base_df(value=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]))

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0


class TestExpectNotNull:
    """Tests for the not_null expectation."""

    def test_not_null_passes(self) -> None:
        """No failures when all values are non-null."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().not_null()))
        df = _base_df(value=[1.0, 2.0, 3.0])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0

    def test_not_null_fails(self) -> None:
        """Null values trigger not_null failure."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().not_null()))
        df = _base_df(value=[1.0, None, 3.0])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        assert exc_info.value.report is not None
        assert exc_info.value.report.failed_count == 1
        assert exc_info.value.report.failures[0].field == "value"
        assert exc_info.value.report.failures[0].expected == "not_null"


class TestExpectGt:
    """Tests for the gt (greater than) expectation."""

    def test_gt_passes(self) -> None:
        """All values above threshold pass."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[1.0, 2.0, 3.0])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0

    def test_gt_fails_for_equal(self) -> None:
        """Value equal to threshold fails gt."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[0.0, 1.0, 2.0])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        assert exc_info.value.report is not None
        assert exc_info.value.report.failed_count == 1

    def test_gt_fails_for_negative(self) -> None:
        """Negative value fails gt(0)."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[-1.0, 1.0, 2.0])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 1
        assert report.failures[0].expected == "gt(0)"


class TestExpectGte:
    """Tests for the gte (greater than or equal) expectation."""

    def test_gte_passes_for_equal(self) -> None:
        """Value equal to threshold passes gte."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER, expect=Expect().gte(1900)))
        df = _base_df(value=[1900, 2000, 2024])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0

    def test_gte_fails_for_below(self) -> None:
        """Value below threshold fails gte."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER, expect=Expect().gte(1900)))
        df = _base_df(value=[1899, 2000, 2024])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        assert exc_info.value.report is not None
        assert exc_info.value.report.failures[0].expected == "gte(1900)"


class TestExpectLt:
    """Tests for the lt (less than) expectation."""

    def test_lt_passes(self) -> None:
        """Values below threshold pass."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().lt(100)))
        df = _base_df(value=[1.0, 50.0, 99.9])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0

    def test_lt_fails_for_equal(self) -> None:
        """Value equal to threshold fails lt."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().lt(100)))
        df = _base_df(value=[100.0, 1.0, 2.0])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        assert exc_info.value.report is not None
        assert exc_info.value.report.failed_count == 1


class TestExpectLte:
    """Tests for the lte (less than or equal) expectation."""

    def test_lte_passes_for_equal(self) -> None:
        """Value equal to threshold passes lte."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER, expect=Expect().lte(2030)))
        df = _base_df(value=[2030, 2000, 1990])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0

    def test_lte_fails_for_above(self) -> None:
        """Value above threshold fails lte."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER, expect=Expect().lte(2030)))
        df = _base_df(value=[2031, 2000, 1990])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        assert exc_info.value.report is not None
        assert exc_info.value.report.failures[0].expected == "lte(2030)"


class TestExpectOneOf:
    """Tests for the one_of expectation."""

    def test_one_of_passes(self) -> None:
        """All values in the allowed set pass."""
        group = _group_with_features(
            Feature(name="value", dtype=FeatureType.STRING, expect=Expect().one_of(["a", "b", "c"]))
        )
        df = _base_df(value=["a", "b", "c"])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0

    def test_one_of_fails(self) -> None:
        """Value not in allowed set fails."""
        group = _group_with_features(
            Feature(name="value", dtype=FeatureType.STRING, expect=Expect().one_of(["a", "b"]))
        )
        df = _base_df(value=["a", "x", "b"])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 1
        assert "one_of" in report.failures[0].expected


class TestCombinedExpectations:
    """Tests for multiple chained constraints on a single feature."""

    def test_not_null_and_gt_combined(self) -> None:
        """Both not_null and gt constraints are enforced."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)))
        # Row 1: null (fails not_null), Row 2: 0.0 (fails gt(0)), Row 3: valid
        df = _base_df(value=[None, 0.0, 5.0])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 2  # rows 0 and 1

    def test_gte_and_lte_range(self) -> None:
        """gte + lte define a valid range."""
        group = _group_with_features(
            Feature(name="value", dtype=FeatureType.INTEGER, expect=Expect().gte(1900).lte(2030))
        )
        df = _base_df(value=[1899, 2031, 2000])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 2  # rows 0 and 1


class TestErrorMode:
    """ERROR mode rejects the entire operation on any failure."""

    def test_error_mode_raises_with_report(self) -> None:
        """ERROR mode raises DataValidationError with a report attached."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[-1.0, 2.0, 3.0])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)

        err = exc_info.value
        assert err.report is not None
        assert err.report.total_count == 3
        assert err.report.passed_count == 2
        assert err.report.failed_count == 1

    def test_error_mode_no_failures_returns_report(self) -> None:
        """ERROR mode with clean data returns report and original DataFrame."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[1.0, 2.0, 3.0])

        report, result_df = validate_data(group, df, ValidationMode.ERROR)
        assert report.failed_count == 0
        assert len(result_df) == 3

    def test_error_message_includes_details(self) -> None:
        """ERROR mode error message includes per-failure details."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[-5.0, 2.0, 3.0])

        with pytest.raises(DataValidationError, match=r"entity_key=.*1.*field='value'.*gt\(0\)"):
            validate_data(group, df, ValidationMode.ERROR)


class TestFilterMode:
    """FILTER mode excludes failing rows and returns passing ones."""

    def test_filter_excludes_failing_rows(self) -> None:
        """Failing rows are removed, passing rows remain."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[-1.0, 2.0, -3.0])

        report, filtered = validate_data(group, df, ValidationMode.FILTER)

        assert report.total_count == 3
        assert report.passed_count == 1
        assert report.failed_count == 2
        assert len(filtered) == 1
        assert filtered["value"].iloc[0] == 2.0

    def test_filter_all_rows_fail(self) -> None:
        """All rows failing returns an empty DataFrame."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(100)))
        df = _base_df(value=[1.0, 2.0, 3.0])

        report, filtered = validate_data(group, df, ValidationMode.FILTER)

        assert report.failed_count == 3
        assert report.passed_count == 0
        assert len(filtered) == 0

    def test_filter_no_failures(self) -> None:
        """No failures returns the full DataFrame."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[1.0, 2.0, 3.0])

        report, filtered = validate_data(group, df, ValidationMode.FILTER)

        assert report.failed_count == 0
        assert len(filtered) == 3

    def test_filter_report_documents_exclusions(self) -> None:
        """Report in FILTER mode includes per-failure details."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[-5.0, 2.0, 3.0])

        report, _ = validate_data(group, df, ValidationMode.FILTER)

        assert len(report.failures) == 1
        assert report.failures[0].field == "value"
        assert report.failures[0].entity_key_value == 1
        assert report.failures[0].expected == "gt(0)"

    def test_filter_resets_index(self) -> None:
        """Filtered DataFrame has a reset integer index."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)))
        df = _base_df(value=[-1.0, 2.0, 3.0])

        _, filtered = validate_data(group, df, ValidationMode.FILTER)

        assert list(filtered.index) == list(range(len(filtered)))


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame returns pass-all report in all modes."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)))
        df = pd.DataFrame(
            {
                "id": pd.Series(dtype="int64"),
                "ts": pd.Series(dtype="datetime64[us]"),
                "value": pd.Series(dtype="float64"),
            }
        )

        for mode in [ValidationMode.ERROR, ValidationMode.FILTER, ValidationMode.NONE]:
            report, result_df = validate_data(group, df, mode)
            assert report.total_count == 0
            assert report.failed_count == 0
            assert len(result_df) == 0

    def test_feature_without_expectations(self) -> None:
        """Feature with no Expect is only type-checked."""
        group = _group_with_features(
            Feature(name="value", dtype=FeatureType.FLOAT)  # no expect
        )
        df = _base_df(value=[1.0, None, 3.0])

        report, _ = validate_data(group, df, ValidationMode.ERROR)
        # Nulls are fine when there's no not_null expectation
        assert report.failed_count == 0

    def test_multiple_features_failures_collected(self) -> None:
        """Failures across multiple features are all collected."""
        group = make_feature_group(
            features=[
                Feature(name="a", dtype=FeatureType.FLOAT, expect=Expect().gt(0)),
                Feature(name="b", dtype=FeatureType.INTEGER, expect=Expect().gte(10)),
            ]
        )
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "a": [-1.0, 5.0],  # row 0 fails gt(0)
                "b": [5, 15],  # row 0 fails gte(10)
            }
        )

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        report = exc_info.value.report
        assert report is not None
        # Row 0 fails on both a and b
        fields = {f.field for f in report.failures}
        assert "a" in fields
        assert "b" in fields


class TestTypeMismatchFilterMode:
    """Type mismatch behaviour in FILTER mode."""

    def test_type_mismatch_filter_mode_excludes_all_rows(self) -> None:
        """Wrong dtype in FILTER mode marks all rows failed, returning empty DataFrame."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER))
        df = _base_df(value=["a", "b", "c"])  # object dtype, not integer

        report, filtered = validate_data(group, df, ValidationMode.FILTER)

        assert report.failed_count == 3
        assert report.passed_count == 0
        assert len(filtered) == 0

    def test_type_mismatch_filter_mode_report_has_column_level_failure(self) -> None:
        """FILTER mode with dtype mismatch: single column-level failure in report."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER))
        df = _base_df(value=["a", "b", "c"])

        report, _ = validate_data(group, df, ValidationMode.FILTER)

        assert len(report.failures) == 1
        assert report.failures[0].field == "value"
        assert report.failures[0].entity_key_value == "*"
        assert "dtype" in report.failures[0].expected

    def test_multiple_columns_wrong_dtype_all_collected(self) -> None:
        """Two features with wrong dtype — both are reported."""
        group = make_feature_group(
            features=[
                Feature(name="a", dtype=FeatureType.INTEGER),
                Feature(name="b", dtype=FeatureType.FLOAT),
            ]
        )
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "a": ["x", "y"],  # object, not integer
                "b": ["p", "q"],  # object, not float
            }
        )

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        report = exc_info.value.report
        assert report is not None
        fields = {f.field for f in report.failures}
        assert "a" in fields
        assert "b" in fields
        # Column-level failures: one per column, not per row
        assert len(report.failures) == 2


class TestNullableIntegerExpectation:
    """Interaction between null-promoted integers and not_null expectation."""

    def test_expectation_on_nullable_integer_column(self) -> None:
        """Integer column with nulls (float64 promotion) passes type check; not_null catches nulls."""
        group = _group_with_features(Feature(name="value", dtype=FeatureType.INTEGER, expect=Expect().not_null()))
        # Pandas promotes int to float64 with nulls — type check should pass
        df = _base_df(value=[1.0, None, 3.0])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 1
        assert report.failures[0].expected == "not_null"


class TestOneOfWithNulls:
    """one_of behaviour with null values."""

    def test_one_of_with_null_values(self) -> None:
        """Null values are not in the allowed set and fail one_of."""
        group = _group_with_features(
            Feature(name="value", dtype=FeatureType.STRING, expect=Expect().one_of(["a", "b"]))
        )
        df = _base_df(value=["a", None, "b"])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, df, ValidationMode.ERROR)
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 1
        assert "one_of" in report.failures[0].expected
