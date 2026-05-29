"""Unit tests for UTC datetime validation on structural and feature columns."""

from __future__ import annotations

import datetime

import pandas as pd
import pytest

from kitefs.enums import FeatureType, ValidationMode
from kitefs.errors import ValidationError
from kitefs.sdk.results import FieldSpec
from kitefs.validation import validate_dataframe
from tests.unit.validation.conftest import make_description

_UTC = datetime.UTC
_ISTANBUL = datetime.timezone(datetime.timedelta(hours=3), "Europe/Istanbul")


def _desc_with_datetime_feature() -> object:
    """Description with a single DATETIME feature (no expectations)."""
    return make_description(
        features=[FieldSpec(name="feat_dt", dtype=FeatureType.DATETIME, description=None, expect=None)]
    )


class TestStructuralUtcValidation:
    """UTC validation for the event_timestamp structural column."""

    def test_naive_event_timestamp_passes(self) -> None:
        """Naive (tz-unaware) datetime64 event_timestamp is treated as UTC and passes."""
        desc = make_description()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),  # naive, no tz
                "value": [1.0],
            }
        )
        assert getattr(frame["ts"].dtype, "tz", None) is None

        _, report = validate_dataframe(desc, frame, ValidationMode.NONE, operation="test")
        assert report is None  # NONE mode; no exception means structural checks passed

    def test_utc_aware_event_timestamp_passes(self) -> None:
        """UTC-aware event_timestamp is accepted."""
        desc = make_description()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]).tz_localize("UTC"),
                "value": [1.0],
            }
        )

        _, report = validate_dataframe(desc, frame, ValidationMode.NONE, operation="test")
        assert report is None

    def test_non_utc_event_timestamp_raises(self) -> None:
        """A non-UTC tz-aware event_timestamp raises ValidationError (structural, all modes)."""
        desc = make_description()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]).tz_localize("Europe/Istanbul"),
                "value": [1.0],
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failures = [f for f in exc_info.value.report.failures if f.field == "ts"]
        assert any(f.constraint == "utc" for f in failures)
        assert failures[0].row_index is None  # column-level

    def test_non_utc_structural_raises_in_none_mode(self) -> None:
        """Structural UTC failure raises even in NONE mode."""
        desc = make_description()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]).tz_localize("Europe/Istanbul"),
                "value": [1.0],
            }
        )

        with pytest.raises(ValidationError):
            validate_dataframe(desc, frame, ValidationMode.NONE, operation="test")


class TestFeatureUtcValidation:
    """UTC validation for DATETIME feature columns."""

    def test_naive_datetime_feature_passes(self) -> None:
        """Naive datetime64 feature column is treated as UTC and passes."""
        desc = _desc_with_datetime_feature()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "feat_dt": pd.to_datetime(["2024-06-01"]),
            }
        )

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0

    def test_utc_aware_datetime_feature_passes(self) -> None:
        """UTC-aware datetime64 feature column is accepted."""
        desc = _desc_with_datetime_feature()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "feat_dt": pd.to_datetime(["2024-06-01"]).tz_localize("UTC"),
            }
        )

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0

    def test_non_utc_datetime_feature_raises(self) -> None:
        """A non-UTC tz-aware datetime64 feature column raises ValidationError."""
        desc = _desc_with_datetime_feature()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "feat_dt": pd.to_datetime(["2024-06-01"]).tz_localize("Europe/Istanbul"),
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failures = [f for f in exc_info.value.report.failures if f.field == "feat_dt"]
        assert any(f.constraint == "utc" for f in failures)
        assert failures[0].row_index is None  # column-level

    def test_non_utc_feature_raises_in_filter_mode(self) -> None:
        """A column-level UTC failure on a feature raises even in FILTER mode."""
        desc = _desc_with_datetime_feature()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "feat_dt": pd.to_datetime(["2024-06-01"]).tz_localize("Europe/Istanbul"),
            }
        )

        with pytest.raises(ValidationError):
            validate_dataframe(desc, frame, ValidationMode.FILTER, operation="test")


class TestObjectColumnDatetimeUtc:
    """UTC validation for object columns of Python datetime objects."""

    def test_naive_python_datetime_in_object_column_passes(self) -> None:
        """A naive Python datetime in an object column is treated as UTC — no failure."""
        desc = _desc_with_datetime_feature()
        naive_dt = datetime.datetime(2024, 6, 1)  # no tzinfo
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "feat_dt": pd.Series([naive_dt], dtype=object),
            }
        )

        _, report = validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")
        assert report is not None and report.fail_count == 0

    def test_non_utc_python_datetime_in_object_column_fails(self) -> None:
        """A non-UTC tz-aware Python datetime in an object column produces a per-row failure."""
        desc = _desc_with_datetime_feature()
        bad_dt = datetime.datetime(2024, 6, 1, tzinfo=_ISTANBUL)
        frame = pd.DataFrame(
            {
                "id": [10],
                "ts": pd.to_datetime(["2024-01-01"]),
                "feat_dt": pd.Series([bad_dt], dtype=object),
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="test")

        failures = [f for f in exc_info.value.report.failures if f.field == "feat_dt"]
        assert len(failures) == 1
        assert failures[0].constraint == "utc"
        assert failures[0].row_index == 0  # positional
        assert failures[0].entity_key_value == 10
