"""Tests for validate_schema (Phase 1 — schema validation)."""

import pandas as pd
import pytest
from helpers import make_feature_group

from kitefs.definitions import (
    Feature,
    FeatureType,
    ValidationMode,
)
from kitefs.exceptions import SchemaValidationError
from kitefs.validation import validate_schema


def _make_valid_df() -> pd.DataFrame:
    """Build a minimal DataFrame matching the default make_feature_group schema."""
    return pd.DataFrame(
        {
            "id": [1, 2],
            "ts": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            "value": [1.0, 2.0],
        }
    )


class TestSchemaValidationSuccess:
    """validate_schema succeeds when all declared columns are present and non-null structural columns."""

    def test_all_columns_present(self) -> None:
        """Schema passes when all declared columns exist with no nulls in structural columns."""
        group = make_feature_group()
        df = _make_valid_df()
        report, cleaned = validate_schema(group, df)

        assert report.total_count == 2
        assert report.passed_count == 2
        assert report.failed_count == 0
        assert report.failures == ()
        assert list(cleaned.columns) == ["id", "ts", "value"]

    def test_empty_dataframe(self) -> None:
        """Schema passes for an empty DataFrame with correct columns (0 rows)."""
        group = make_feature_group()
        df = pd.DataFrame(
            {
                "id": pd.Series(dtype="int64"),
                "ts": pd.Series(dtype="datetime64[us]"),
                "value": pd.Series(dtype="float64"),
            }
        )
        report, cleaned = validate_schema(group, df)

        assert report.total_count == 0
        assert report.passed_count == 0
        assert report.failed_count == 0
        assert len(cleaned) == 0

    def test_extra_columns_dropped(self) -> None:
        """Extra columns in the DataFrame are silently dropped."""
        group = make_feature_group()
        df = _make_valid_df()
        df["extra_col"] = "ignored"
        df["another_extra"] = 99

        report, cleaned = validate_schema(group, df)

        assert "extra_col" not in cleaned.columns
        assert "another_extra" not in cleaned.columns
        assert list(cleaned.columns) == ["id", "ts", "value"]
        assert report.total_count == 2

    def test_column_order_matches_definition(self) -> None:
        """Returned DataFrame columns follow definition order: entity_key, event_timestamp, features."""
        group = make_feature_group(
            features=[
                Feature(name="b_feat", dtype=FeatureType.FLOAT),
                Feature(name="a_feat", dtype=FeatureType.INTEGER),
            ]
        )
        # Features are sorted alphabetically by FeatureGroup.__post_init__
        df = pd.DataFrame(
            {
                "b_feat": [1.0],
                "a_feat": [10],
                "ts": pd.to_datetime(["2024-01-01"]),
                "id": [1],
            }
        )
        _, cleaned = validate_schema(group, df)
        # a_feat comes before b_feat (sorted), after structural columns
        assert list(cleaned.columns) == ["id", "ts", "a_feat", "b_feat"]


class TestSchemaValidationMissingColumns:
    """validate_schema raises SchemaValidationError for missing columns."""

    def test_missing_feature_column(self) -> None:
        """Missing feature column is reported."""
        group = make_feature_group()
        df = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                # "value" is missing
            }
        )
        with pytest.raises(SchemaValidationError, match=r"Missing required column.*value"):
            validate_schema(group, df)

    def test_missing_entity_key(self) -> None:
        """Missing entity key column is reported."""
        group = make_feature_group()
        df = pd.DataFrame(
            {
                "ts": pd.to_datetime(["2024-01-01"]),
                "value": [1.0],
            }
        )
        with pytest.raises(SchemaValidationError, match=r"Missing required column.*id"):
            validate_schema(group, df)

    def test_missing_event_timestamp(self) -> None:
        """Missing event timestamp column is reported."""
        group = make_feature_group()
        df = pd.DataFrame(
            {
                "id": [1],
                "value": [1.0],
            }
        )
        with pytest.raises(SchemaValidationError, match=r"Missing required column.*ts"):
            validate_schema(group, df)

    def test_multiple_missing_columns_all_reported(self) -> None:
        """All missing columns are listed in a single error."""
        group = make_feature_group(
            features=[
                Feature(name="feat_a", dtype=FeatureType.FLOAT),
                Feature(name="feat_b", dtype=FeatureType.STRING),
            ]
        )
        df = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                # feat_a and feat_b both missing
            }
        )
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_schema(group, df)
        msg = str(exc_info.value)
        assert "feat_a" in msg
        assert "feat_b" in msg


class TestSchemaValidationNullStructural:
    """validate_schema raises SchemaValidationError for null structural columns."""

    def test_null_entity_key(self) -> None:
        """Null values in entity key column are a schema failure."""
        group = make_feature_group()
        df = pd.DataFrame(
            {
                "id": [1, None, 3],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                "value": [1.0, 2.0, 3.0],
            }
        )
        with pytest.raises(SchemaValidationError, match="Entity key column 'id' contains 1 null"):
            validate_schema(group, df)

    def test_null_event_timestamp(self) -> None:
        """Null values in event timestamp column are a schema failure."""
        group = make_feature_group()
        ts = pd.Series(pd.to_datetime(["2024-01-01", "2024-02-01"]))
        ts.iloc[1] = None  # type: ignore[assignment]  # introduces NaT
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": ts,
                "value": [1.0, 2.0],
            }
        )
        with pytest.raises(SchemaValidationError, match="Event timestamp column 'ts' contains 1 null"):
            validate_schema(group, df)

    def test_both_nulls_reported_together(self) -> None:
        """Both null entity key and null timestamp are reported in one error."""
        group = make_feature_group()
        ts = pd.Series(pd.to_datetime(["2024-01-01", "2024-02-01"]))
        ts.iloc[0] = None  # type: ignore[assignment]  # introduces NaT
        df = pd.DataFrame(
            {
                "id": [None, 2],
                "ts": ts,
                "value": [1.0, 2.0],
            }
        )
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_schema(group, df)
        msg = str(exc_info.value)
        assert "Entity key column 'id'" in msg
        assert "Event timestamp column 'ts'" in msg

    def test_missing_and_null_combined(self) -> None:
        """Missing columns and null structural columns are all reported together."""
        group = make_feature_group(
            features=[
                Feature(name="a", dtype=FeatureType.FLOAT),
                Feature(name="b", dtype=FeatureType.STRING),
            ]
        )
        df = pd.DataFrame(
            {
                "id": [None],
                "ts": pd.to_datetime(["2024-01-01"]),
                # a is present, b is missing
                "a": [1.0],
            }
        )
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_schema(group, df)
        msg = str(exc_info.value)
        assert "Missing required column" in msg
        assert "b" in msg
        assert "Entity key column 'id'" in msg


class TestSchemaValidationIsHardGate:
    """Schema validation is mode-independent — it always uses ERROR semantics."""

    def test_schema_failure_regardless_of_mode(self) -> None:
        """Even with NONE or FILTER mode on the group, schema validation still raises."""
        group = make_feature_group(
            ingestion_validation=ValidationMode.NONE,
            offline_retrieval_validation=ValidationMode.FILTER,
        )
        df = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                # "value" missing
            }
        )
        # validate_schema does not accept a mode — it always raises
        with pytest.raises(SchemaValidationError):
            validate_schema(group, df)


class TestSchemaErrorReport:
    """validate_schema attaches a structured report to the exception."""

    def test_schema_error_has_report_attached(self) -> None:
        """SchemaValidationError carries a non-None report with correct counts."""
        group = make_feature_group()
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                # "value" missing
            }
        )
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_schema(group, df)

        report = exc_info.value.report
        assert report is not None
        assert report.total_count == 3
        assert report.failed_count == 3
        assert report.passed_count == 0
        assert len(report.failures) >= 1
        assert report.failures[0].field == "_schema"

    def test_null_structural_error_report_has_total_count(self) -> None:
        """Null structural column error report reflects correct total row count."""
        group = make_feature_group()
        df = pd.DataFrame(
            {
                "id": [None, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "value": [1.0, 2.0],
            }
        )
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_schema(group, df)

        report = exc_info.value.report
        assert report is not None
        assert report.total_count == 2
