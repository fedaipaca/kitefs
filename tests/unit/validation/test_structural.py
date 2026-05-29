"""Unit tests for structural validation (null, dtype, UTC on structural columns)."""

from __future__ import annotations

import pandas as pd
import pytest

from kitefs.enums import FeatureType, ValidationMode
from kitefs.errors import ValidationError
from kitefs.validation import validate_dataframe
from tests.unit.validation.conftest import make_description

_ALL_MODES = [
    pytest.param(ValidationMode.ERROR, id="error_mode"),
    pytest.param(ValidationMode.FILTER, id="filter_mode"),
    pytest.param(ValidationMode.NONE, id="none_mode"),
]


def _valid_frame() -> pd.DataFrame:
    """Minimal valid frame for the default make_description() schema (id, ts, value)."""
    return pd.DataFrame(
        {
            "id": [1],
            "ts": pd.to_datetime(["2024-01-01"]),
            "value": [1.0],
        }
    )


class TestNullEntityKey:
    """A null entity key raises ValidationError in every mode."""

    @pytest.mark.parametrize("mode", _ALL_MODES)
    def test_null_entity_key_raises(self, mode: ValidationMode) -> None:
        """Null entity key value raises ValidationError regardless of mode."""
        desc = make_description()
        # Int64 (nullable integer) preserves integer dtype with a null value.
        frame = pd.DataFrame(
            {
                "id": pd.array([None], dtype="Int64"),
                "ts": pd.to_datetime(["2024-01-01"]),
                "value": [1.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, mode, operation="ingestion")

        report = exc_info.value.report
        assert any(f.field == "id" and f.constraint == "not_null" for f in report.failures)

    def test_failure_has_correct_row_index(self) -> None:
        """ValidationFailure for a null entity key records the positional row index."""
        desc = make_description()
        # Use Int64 (nullable integer) so None doesn't promote the column to float64.
        frame = pd.DataFrame(
            {
                "id": pd.array([1, None, 3], dtype="Int64"),
                "ts": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                "value": [1.0, 2.0, 3.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        failures = [f for f in exc_info.value.report.failures if f.field == "id" and f.constraint == "not_null"]
        assert len(failures) == 1
        assert failures[0].row_index == 1


class TestNullEventTimestamp:
    """A null event timestamp raises ValidationError in every mode."""

    @pytest.mark.parametrize("mode", _ALL_MODES)
    def test_null_event_timestamp_raises(self, mode: ValidationMode) -> None:
        """Null event timestamp value raises ValidationError regardless of mode."""
        desc = make_description()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": [None],
                "value": [1.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, mode, operation="ingestion")

        report = exc_info.value.report
        assert any(f.field == "ts" and f.constraint == "not_null" for f in report.failures)


class TestStructuralDtypeMismatch:
    """Incompatible dtype on a structural column raises ValidationError."""

    def test_string_in_integer_entity_key_raises(self) -> None:
        """A string-dtype entity key declared as INTEGER raises ValidationError."""
        desc = make_description(entity_key_dtype=FeatureType.INTEGER)
        frame = pd.DataFrame(
            {
                "id": ["not_an_int"],
                "ts": pd.to_datetime(["2024-01-01"]),
                "value": [1.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        failures = [f for f in exc_info.value.report.failures if f.field == "id"]
        assert any(f.constraint == "dtype(INTEGER)" for f in failures)

    def test_float_in_integer_entity_key_raises(self) -> None:
        """A float-dtype entity key declared as INTEGER raises ValidationError."""
        desc = make_description(entity_key_dtype=FeatureType.INTEGER)
        frame = pd.DataFrame(
            {
                "id": [1.5],
                "ts": pd.to_datetime(["2024-01-01"]),
                "value": [1.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        failures = [f for f in exc_info.value.report.failures if f.field == "id"]
        assert any("dtype" in f.constraint for f in failures)

    @pytest.mark.parametrize("mode", _ALL_MODES)
    def test_structural_dtype_failure_raises_in_all_modes(self, mode: ValidationMode) -> None:
        """A structural dtype mismatch raises ValidationError in every mode."""
        desc = make_description(entity_key_dtype=FeatureType.INTEGER)
        frame = pd.DataFrame(
            {
                "id": ["bad"],
                "ts": pd.to_datetime(["2024-01-01"]),
                "value": [1.0],
            }
        )

        with pytest.raises(ValidationError):
            validate_dataframe(desc, frame, mode, operation="ingestion")


class TestValidStructuralColumns:
    """Valid structural columns produce no failures."""

    def test_valid_integer_entity_key_passes(self) -> None:
        """An integer-dtype entity key declared as INTEGER passes structural checks."""
        desc = make_description(entity_key_dtype=FeatureType.INTEGER)
        frame = _valid_frame()
        result_frame, report = validate_dataframe(desc, frame, ValidationMode.NONE, operation="ingestion")
        assert report is None
        assert len(result_frame) == 1

    def test_entity_key_value_populated_in_failure(self) -> None:
        """ValidationFailure.entity_key_value reflects the entity key for that failing row."""
        desc = make_description()
        # Use a null event_timestamp to produce a failure while keeping id integer.
        frame = pd.DataFrame(
            {
                "id": [7, 8],
                "ts": [pd.Timestamp("2024-01-01"), None],
                "value": [1.0, 2.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        ts_null_failures = [f for f in exc_info.value.report.failures if f.field == "ts" and f.constraint == "not_null"]
        assert len(ts_null_failures) == 1
        assert ts_null_failures[0].row_index == 1
        assert ts_null_failures[0].entity_key_value == 8  # entity key for the failing row
