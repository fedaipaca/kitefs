"""Unit tests for feature expectation evaluation (not_null, gt, gte, lt, lte, is_in)."""

from __future__ import annotations

import pandas as pd
import pytest

from kitefs.enums import FeatureType, ValidationMode
from kitefs.errors import ValidationError
from kitefs.sdk.results import FieldSpec
from kitefs.validation import validate_dataframe
from tests.unit.validation.conftest import make_description


def _desc_with_expect(expect: list) -> object:
    """Description with one FLOAT feature carrying the given serialized expectations."""
    return make_description(features=[FieldSpec(name="feat", dtype=FeatureType.FLOAT, description=None, expect=expect)])


def _frame(values: list) -> pd.DataFrame:
    """One-feature frame with the given feature values."""
    return pd.DataFrame(
        {
            "id": list(range(len(values))),
            "ts": pd.to_datetime(["2024-01-01"] * len(values)),
            "feat": values,
        }
    )


class TestNotNull:
    """not_null expectation rejects null feature values."""

    def test_null_value_fails(self) -> None:
        """A null feature value violates not_null."""
        desc = _desc_with_expect([{"type": "not_null"}])
        frame = _frame([None])

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failures = exc_info.value.report.failures
        assert len(failures) == 1
        assert failures[0].constraint == "not_null"
        assert failures[0].field == "feat"
        assert failures[0].actual_value is None
        assert failures[0].row_index == 0

    def test_non_null_value_passes(self) -> None:
        """A non-null feature value satisfies not_null."""
        desc = _desc_with_expect([{"type": "not_null"}])
        frame = _frame([42.0])

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0


class TestGt:
    """gt expectation rejects values not strictly greater than threshold."""

    def test_value_above_threshold_passes(self) -> None:
        """A value greater than the threshold satisfies gt."""
        desc = _desc_with_expect([{"type": "gt", "value": 0}])
        frame = _frame([1.0])

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0

    def test_value_equal_to_threshold_fails(self) -> None:
        """A value equal to the threshold violates gt (strict greater-than)."""
        desc = _desc_with_expect([{"type": "gt", "value": 0}])
        frame = _frame([0.0])

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failures = exc_info.value.report.failures
        assert failures[0].constraint == "gt(0)"
        assert failures[0].actual_value == 0.0

    def test_value_below_threshold_fails(self) -> None:
        """A value below the threshold violates gt."""
        desc = _desc_with_expect([{"type": "gt", "value": 0}])
        frame = _frame([-10.0])

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        assert exc_info.value.report.failures[0].actual_value == -10.0

    def test_constraint_string_format(self) -> None:
        """Constraint string matches the spec example: 'gt(0)'."""
        desc = _desc_with_expect([{"type": "gt", "value": 0}])
        frame = _frame([-1.0])

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        assert exc_info.value.report.failures[0].constraint == "gt(0)"

    def test_null_skipped_by_gt(self) -> None:
        """gt does not flag null values — that belongs to not_null."""
        desc = _desc_with_expect([{"type": "gt", "value": 0}])
        frame = _frame([None])

        # Without not_null, a null value should NOT produce a gt failure
        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0


class TestGte:
    """gte expectation rejects values strictly less than threshold."""

    @pytest.mark.parametrize(
        ("value", "fails"),
        [
            pytest.param(5.0, False, id="above_passes"),
            pytest.param(5.0, False, id="equal_passes"),
            pytest.param(4.9, True, id="below_fails"),
        ],
    )
    def test_gte(self, value: float, fails: bool) -> None:
        """gte passes at-or-above threshold and fails below."""
        desc = _desc_with_expect([{"type": "gte", "value": 5}])
        frame = _frame([value])

        if fails:
            with pytest.raises(ValidationError) as exc_info:
                validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
            assert "gte(5)" in exc_info.value.report.failures[0].constraint
        else:
            _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
            assert report is not None and report.fail_count == 0


class TestLt:
    """lt expectation rejects values >= threshold."""

    @pytest.mark.parametrize(
        ("value", "fails"),
        [
            pytest.param(99.0, False, id="below_passes"),
            pytest.param(100.0, True, id="equal_fails"),
            pytest.param(101.0, True, id="above_fails"),
        ],
    )
    def test_lt(self, value: float, fails: bool) -> None:
        """lt passes strictly below threshold and fails at-or-above."""
        desc = _desc_with_expect([{"type": "lt", "value": 100}])
        frame = _frame([value])

        if fails:
            with pytest.raises(ValidationError) as exc_info:
                validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
            assert "lt(100)" in exc_info.value.report.failures[0].constraint
        else:
            _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
            assert report is not None and report.fail_count == 0


class TestLte:
    """lte expectation rejects values strictly greater than threshold."""

    @pytest.mark.parametrize(
        ("value", "fails"),
        [
            pytest.param(10.0, False, id="below_passes"),
            pytest.param(10.0, False, id="equal_passes"),
            pytest.param(10.1, True, id="above_fails"),
        ],
    )
    def test_lte(self, value: float, fails: bool) -> None:
        """lte passes at-or-below threshold and fails above."""
        desc = _desc_with_expect([{"type": "lte", "value": 10}])
        frame = _frame([value])

        if fails:
            with pytest.raises(ValidationError):
                validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        else:
            _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
            assert report is not None and report.fail_count == 0


class TestIsIn:
    """is_in expectation rejects values not in the allowed set."""

    def test_value_in_set_passes(self) -> None:
        """A value that is in the allowed set satisfies is_in."""
        desc = _desc_with_expect([{"type": "is_in", "value": [1.0, 2.0, 3.0]}])
        frame = _frame([2.0])

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0

    def test_value_not_in_set_fails(self) -> None:
        """A value outside the allowed set violates is_in."""
        desc = _desc_with_expect([{"type": "is_in", "value": [1.0, 2.0, 3.0]}])
        frame = _frame([99.0])

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        assert "is_in" in exc_info.value.report.failures[0].constraint

    def test_null_skipped_by_is_in(self) -> None:
        """is_in does not flag null values — that belongs to not_null."""
        desc = _desc_with_expect([{"type": "is_in", "value": [1.0, 2.0]}])
        frame = _frame([None])

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0


class TestChainedExpectations:
    """Multiple expectations on one feature produce separate failures."""

    def test_not_null_and_gt_both_fail(self) -> None:
        """A null value triggers not_null but not gt; a negative value triggers gt."""
        desc = _desc_with_expect([{"type": "not_null"}, {"type": "gt", "value": 0}])
        frame = _frame([None, -5.0])

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failures = exc_info.value.report.failures
        constraints = {f.constraint for f in failures}
        # Row 0 (None) fails not_null; gt skips it (null)
        # Row 1 (-5.0) fails gt; not_null passes
        assert "not_null" in constraints
        assert "gt(0)" in constraints
        assert len(failures) == 2

    def test_failure_entity_key_value_populated(self) -> None:
        """Failure records entity_key_value from the row that failed."""
        desc = _desc_with_expect([{"type": "gt", "value": 0}])
        frame = pd.DataFrame(
            {
                "id": [3],
                "ts": pd.to_datetime(["2024-02-01"]),
                "feat": [-10.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failure = exc_info.value.report.failures[0]
        assert failure.entity_key_value == 3
        assert failure.actual_value == -10.0
        assert failure.row_index == 0
