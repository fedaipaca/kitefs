"""Unit tests for ValidationMode-specific behavior (NONE, ERROR, FILTER)."""

from __future__ import annotations

import pandas as pd
import pytest

from kitefs.enums import FeatureType, ValidationMode
from kitefs.errors import ValidationError
from kitefs.sdk.results import FeatureGroupDescription, FieldSpec
from kitefs.validation import validate_dataframe
from tests.unit.validation.conftest import make_description


def _desc_with_gt_0() -> FeatureGroupDescription:
    """Description with a single FLOAT feature expecting gt(0)."""
    return make_description(
        features=[
            FieldSpec(name="value", dtype=FeatureType.FLOAT, description=None, expect=[{"type": "gt", "value": 0}])
        ]
    )


def _two_row_frame(good_val: float, bad_val: float) -> pd.DataFrame:
    """Two-row frame: row 0 is good, row 1 is bad (fails gt(0))."""
    return pd.DataFrame(
        {
            "id": [1, 2],
            "ts": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "value": [good_val, bad_val],
        }
    )


class TestNoneMode:
    """NONE mode skips feature checks and returns (frame, None)."""

    def test_returns_original_frame_and_none_report(self) -> None:
        """NONE mode returns the original DataFrame and None as report."""
        desc = _desc_with_gt_0()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "value": [-999.0],  # would fail gt(0) in ERROR mode
            }
        )

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.NONE, operation="test")

        assert report is None
        assert result_frame is frame  # same object, no copy

    def test_skips_feature_checks_for_bad_values(self) -> None:
        """NONE mode does not raise even when feature values violate expectations."""
        desc = _desc_with_gt_0()
        frame = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "value": [-1.0, -2.0],  # both fail gt(0)
            }
        )

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.NONE, operation="test")
        assert report is None
        assert len(result_frame) == 2


class TestErrorMode:
    """ERROR mode raises ValidationError on any feature failure."""

    def test_all_valid_rows_return_pass_only_report(self) -> None:
        """All-valid rows in ERROR mode return the frame and a pass-only report."""
        desc = _desc_with_gt_0()
        frame = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "value": [1.0, 2.0],
            }
        )

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        assert report is not None
        assert report.pass_count == 2
        assert report.fail_count == 0
        assert report.failures == []
        assert len(result_frame) == 2

    def test_single_failing_row_raises_with_report(self) -> None:
        """A single failing row raises ValidationError carrying a ValidationReport."""
        desc = _desc_with_gt_0()
        frame = _two_row_frame(1.0, -10.0)

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        report = exc_info.value.report
        assert report.fail_count == 1
        assert report.pass_count == 1
        assert len(report.failures) == 1

    def test_failure_fields_populated_correctly(self) -> None:
        """ValidationFailure carries field, constraint, actual_value, entity_key_value, row_index."""
        desc = _desc_with_gt_0()
        frame = pd.DataFrame(
            {
                "id": [3],
                "ts": pd.to_datetime(["2024-02-01"]),
                "value": [-10.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        f = exc_info.value.report.failures[0]
        assert f.field == "value"
        assert f.constraint == "gt(0)"
        assert f.actual_value == -10.0
        assert f.entity_key_value == 3
        assert f.row_index == 0


class TestFilterMode:
    """FILTER mode drops failing rows and returns passing subset with report."""

    def test_passing_row_kept_failing_row_dropped(self) -> None:
        """FILTER mode returns only the rows that pass all expectations."""
        desc = _desc_with_gt_0()
        frame = _two_row_frame(24500.0, -10.0)  # row 0 good, row 1 bad

        result_frame, _ = validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")

        assert len(result_frame) == 1
        assert result_frame.iloc[0]["id"] == 1  # the good row

    def test_report_counts_match_dropped_rows(self) -> None:
        """FILTER report has pass_count = kept rows and fail_count = dropped rows."""
        desc = _desc_with_gt_0()
        frame = _two_row_frame(1.0, -1.0)

        _, report = validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")

        assert report is not None
        assert report.pass_count == 1
        assert report.fail_count == 1

    def test_all_passing_returns_full_frame(self) -> None:
        """FILTER with no failures returns the original frame and a pass-only report."""
        desc = _desc_with_gt_0()
        frame = _two_row_frame(5.0, 10.0)

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")

        assert len(result_frame) == 2
        assert report is not None
        assert report.pass_count == 2
        assert report.fail_count == 0

    def test_all_failing_returns_empty_frame(self) -> None:
        """FILTER with all failures returns an empty DataFrame."""
        desc = _desc_with_gt_0()
        frame = _two_row_frame(-1.0, -2.0)

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")

        assert len(result_frame) == 0
        assert report is not None
        assert report.pass_count == 0
        assert report.fail_count == 2

    def test_row_failing_two_checks_dropped_once(self) -> None:
        """A row that fails two expectations is dropped once (fail_count counts distinct rows)."""
        desc = make_description(
            features=[
                FieldSpec(
                    name="value",
                    dtype=FeatureType.FLOAT,
                    description=None,
                    expect=[{"type": "not_null"}, {"type": "gt", "value": 0}],
                )
            ]
        )
        # Row 0: null — fails not_null, gt skips it; row 1: negative — fails gt
        frame = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "value": [None, -5.0],
            }
        )

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")

        # Both rows dropped — they each fail one distinct check
        assert len(result_frame) == 0
        assert report is not None
        assert report.fail_count == 2  # 2 distinct rows dropped
        assert report.pass_count == 0
        assert len(report.failures) == 2  # 2 failure records

    def test_feature_dtype_fault_drops_rows_in_filter_mode(self) -> None:
        """A dtype mismatch in FILTER mode drops the failing rows instead of raising."""
        desc = make_description(
            features=[FieldSpec(name="value", dtype=FeatureType.INTEGER, description=None, expect=None)]
        )
        # float64 values for an INTEGER feature — per-row dtype failures, all dropped in FILTER
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "value": [1.5],
            }
        )

        result_frame, report = validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")

        assert len(result_frame) == 0
        assert report is not None
        assert report.fail_count == 1
        assert any("dtype(INTEGER)" in f.constraint for f in report.failures)
