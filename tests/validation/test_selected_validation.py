"""Tests for validate_data_selected (retrieval-path validation on feature subsets)."""

import pandas as pd
import pytest
from helpers import make_feature_group

from kitefs.definitions import (
    Expect,
    Feature,
    FeatureType,
    ValidationMode,
)
from kitefs.exceptions import DataValidationError, SchemaValidationError
from kitefs.validation import validate_data, validate_data_selected


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


# Two features used across multiple tests
_FEAT_A = Feature(name="a", dtype=FeatureType.FLOAT, expect=Expect().not_null())
_FEAT_B = Feature(name="b", dtype=FeatureType.INTEGER, expect=Expect().gt(0))


class TestSubsetSelection:
    """Selecting a subset of features ignores unselected columns."""

    def test_invalid_unselected_feature_does_not_block_retrieval(self) -> None:
        """Invalid data in an unselected feature must not cause validation failure."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        # b has invalid data (negatives), but we only select a
        df = _base_df(a=[1.0, 2.0, 3.0], b=[-1, -2, -3])

        report, result_df = validate_data_selected(group, df, ValidationMode.ERROR, ["a"])

        assert report.failed_count == 0
        assert len(result_df) == 3

    def test_absent_unselected_column_does_not_cause_error(self) -> None:
        """DataFrame missing an unselected feature column entirely must not fail.

        This is the real regression case: Task 14 passes a select-narrowed
        DataFrame where unselected feature columns are absent, not just
        carrying bad data.
        """
        group = _group_with_features(_FEAT_A, _FEAT_B)
        # DataFrame has only structural columns + selected feature 'a'; 'b' is absent
        df = _base_df(a=[1.0, 2.0, 3.0])

        report, result_df = validate_data_selected(group, df, ValidationMode.ERROR, ["a"])

        assert report.failed_count == 0
        assert len(result_df) == 3

    def test_invalid_selected_feature_raises_in_error_mode(self) -> None:
        """Invalid data in a selected feature raises DataValidationError."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        # a has nulls (fails not_null), b is fine
        df = _base_df(a=[None, 2.0, 3.0], b=[1, 2, 3])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data_selected(group, df, ValidationMode.ERROR, ["a"])
        assert exc_info.value.report is not None
        assert exc_info.value.report.failed_count == 1

    def test_missing_selected_column_raises_schema_error(self) -> None:
        """Selecting a feature whose column is absent raises SchemaValidationError."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        # DataFrame has only structural columns — both feature columns absent
        df = _base_df()

        with pytest.raises(SchemaValidationError, match=r"Selected feature column.*missing"):
            validate_data_selected(group, df, ValidationMode.ERROR, ["a"])


class TestAllFeaturesSelected:
    """Selecting all features behaves identically to validate_data."""

    def test_all_selected_matches_validate_data_pass(self) -> None:
        """Selecting all features with valid data produces identical report and DataFrame."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        df = _base_df(a=[1.0, 2.0, 3.0], b=[10, 20, 30])

        report_selected, df_selected = validate_data_selected(group, df, ValidationMode.ERROR, ["a", "b"])
        report_full, df_full = validate_data(group, df, ValidationMode.ERROR)

        assert report_selected.total_count == report_full.total_count
        assert report_selected.passed_count == report_full.passed_count
        assert report_selected.failed_count == report_full.failed_count
        assert report_selected.failures == report_full.failures
        pd.testing.assert_frame_equal(df_selected, df_full)

    def test_all_selected_matches_validate_data_error(self) -> None:
        """Selecting all features with invalid data raises the same error with matching details."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        df = _base_df(a=[None, 2.0, 3.0], b=[1, 2, 3])

        with pytest.raises(DataValidationError) as exc_selected:
            validate_data_selected(group, df, ValidationMode.ERROR, ["a", "b"])
        with pytest.raises(DataValidationError) as exc_full:
            validate_data(group, df, ValidationMode.ERROR)

        report_sel = exc_selected.value.report
        report_ful = exc_full.value.report
        assert report_sel is not None
        assert report_ful is not None
        assert report_sel.failed_count == report_ful.failed_count
        assert len(report_sel.failures) == len(report_ful.failures)
        for fs, ff in zip(report_sel.failures, report_ful.failures, strict=True):
            assert fs.field == ff.field
            assert fs.expected == ff.expected
            assert fs.actual == ff.actual


class TestErrorMode:
    """ERROR mode raises on selected feature failures."""

    def test_error_mode_raises_on_selected_failure(self) -> None:
        """DataValidationError raised when a selected feature has invalid data."""
        group = _group_with_features(Feature(name="price", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)))
        df = _base_df(price=[0.0, 100.0, 200.0])  # 0.0 fails gt(0)

        with pytest.raises(DataValidationError) as exc_info:
            validate_data_selected(group, df, ValidationMode.ERROR, ["price"])
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 1
        assert report.failures[0].field == "price"
        assert report.failures[0].expected == "gt(0)"


class TestFilterMode:
    """FILTER mode excludes failing rows from selected features."""

    def test_filter_mode_excludes_failing_rows(self) -> None:
        """Rows failing selected-feature expectations are filtered out."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        # a has a null in row 0 (fails not_null)
        df = _base_df(a=[None, 2.0, 3.0], b=[1, 2, 3])

        report, result_df = validate_data_selected(group, df, ValidationMode.FILTER, ["a"])

        assert report.failed_count == 1
        assert len(result_df) == 2

    def test_filter_mode_ignores_unselected_failures(self) -> None:
        """Rows failing only in unselected features are not filtered."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        # b has negatives (fails gt(0)), but only a is selected
        df = _base_df(a=[1.0, 2.0, 3.0], b=[-1, -2, -3])

        report, result_df = validate_data_selected(group, df, ValidationMode.FILTER, ["a"])

        assert report.failed_count == 0
        assert len(result_df) == 3


class TestNoneMode:
    """NONE mode skips validation entirely."""

    def test_none_mode_skips_all_checks(self) -> None:
        """NONE mode returns pass-all report regardless of data quality."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        # Both features have bad data
        df = _base_df(a=[None, None, None], b=[-1, -2, -3])

        report, result_df = validate_data_selected(group, df, ValidationMode.NONE, ["a", "b"])

        assert report.total_count == 3
        assert report.passed_count == 3
        assert report.failed_count == 0
        assert len(result_df) == 3


class TestEmptySelection:
    """Empty selected_features list means only structural columns are in the DataFrame."""

    def test_empty_selection_passes_trivially(self) -> None:
        """No features selected — validation has nothing to check, passes."""
        group = _group_with_features(_FEAT_A, _FEAT_B)
        # DataFrame has only structural columns
        df = _base_df()

        report, result_df = validate_data_selected(group, df, ValidationMode.ERROR, [])

        assert report.total_count == 3
        assert report.passed_count == 3
        assert report.failed_count == 0
        assert len(result_df) == 3

    def test_empty_selection_in_filter_mode(self) -> None:
        """FILTER mode with no features selected keeps all rows."""
        group = _group_with_features(_FEAT_A)
        df = _base_df()

        report, result_df = validate_data_selected(group, df, ValidationMode.FILTER, [])

        assert report.failed_count == 0
        assert len(result_df) == 3


class TestExpectationsEvaluated:
    """Expect constraints are correctly evaluated on selected features."""

    def test_chained_expectations_on_selected_feature(self) -> None:
        """Multiple chained expectations are all evaluated on a selected feature."""
        feat = Feature(
            name="year",
            dtype=FeatureType.INTEGER,
            expect=Expect().not_null().gte(1900).lte(2030),
        )
        group = _group_with_features(feat)
        # 1800 fails gte(1900), 2050 fails lte(2030)
        df = _base_df(year=[1800, 2000, 2050])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data_selected(group, df, ValidationMode.ERROR, ["year"])
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 2

    def test_one_of_expectation_on_selected_feature(self) -> None:
        """one_of expectation is evaluated correctly on a selected feature."""
        feat = Feature(
            name="category",
            dtype=FeatureType.STRING,
            expect=Expect().one_of(["apartment", "house"]),
        )
        group = _group_with_features(feat)
        df = _base_df(category=["apartment", "house", "land"])

        with pytest.raises(DataValidationError) as exc_info:
            validate_data_selected(group, df, ValidationMode.ERROR, ["category"])
        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 1
        assert report.failures[0].field == "category"


class TestImportability:
    """validate_data_selected is importable from kitefs.validation."""

    def test_importable_from_validation_module(self) -> None:
        """The function is an internal API in the validation module."""
        from kitefs.validation import validate_data_selected as fn

        assert callable(fn)
