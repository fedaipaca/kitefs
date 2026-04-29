"""Integration tests — Phase 1 as hard gate for Phase 2, full two-phase flow."""

import pandas as pd
import pytest

from kitefs.definitions import (
    EntityKey,
    EventTimestamp,
    Expect,
    Feature,
    FeatureGroup,
    FeatureType,
    JoinKey,
    Metadata,
    StorageTarget,
    ValidationMode,
)
from kitefs.exceptions import DataValidationError, SchemaValidationError
from kitefs.validation import validate_data, validate_schema

# ---------------------------------------------------------------------------
# Phase 1 → Phase 2 gate
# ---------------------------------------------------------------------------


class TestTwoPhaseGate:
    """Schema validation (Phase 1) must pass before data validation (Phase 2) runs."""

    def test_schema_failure_blocks_data_validation(self) -> None:
        """If schema fails, data validation is never reached."""
        group = FeatureGroup(
            name="test",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
            features=[Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0))],
        )
        # Missing column → Phase 1 fails
        df = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                # "value" missing
            }
        )

        with pytest.raises(SchemaValidationError):
            validate_schema(group, df)
        # validate_data should never be called — but even if called, schema was bad
        # The contract is: caller runs Phase 1 first, only proceeds to Phase 2 on success.

    def test_full_flow_schema_pass_data_pass(self) -> None:
        """Clean data passes both phases."""
        group = FeatureGroup(
            name="test",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
            features=[Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0))],
        )
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "value": [10.0, 20.0],
            }
        )

        schema_report, cleaned_df = validate_schema(group, df)
        assert schema_report.failed_count == 0

        data_report, result_df = validate_data(group, cleaned_df, ValidationMode.ERROR)
        assert data_report.failed_count == 0
        assert len(result_df) == 2

    def test_full_flow_schema_pass_data_error(self) -> None:
        """Schema passes but data validation raises in ERROR mode."""
        group = FeatureGroup(
            name="test",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
            features=[Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0))],
        )
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "value": [-5.0, 20.0],
            }
        )

        schema_report, cleaned_df = validate_schema(group, df)
        assert schema_report.failed_count == 0

        with pytest.raises(DataValidationError):
            validate_data(group, cleaned_df, ValidationMode.ERROR)

    def test_full_flow_schema_pass_data_filter(self) -> None:
        """Schema passes, FILTER mode excludes failing rows."""
        group = FeatureGroup(
            name="test",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
            features=[Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0))],
        )
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                "value": [-5.0, 20.0, -1.0],
            }
        )

        schema_report, cleaned_df = validate_schema(group, df)
        assert schema_report.failed_count == 0

        data_report, filtered_df = validate_data(group, cleaned_df, ValidationMode.FILTER)
        assert data_report.failed_count == 2
        assert len(filtered_df) == 1
        assert filtered_df["value"].iloc[0] == 20.0

    def test_full_flow_schema_pass_data_none(self) -> None:
        """Schema passes, NONE mode skips data validation entirely."""
        group = FeatureGroup(
            name="test",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
            features=[Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0))],
        )
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "value": [-999.0, -888.0],  # would fail gt(0) but mode is NONE
            }
        )

        schema_report, cleaned_df = validate_schema(group, df)
        assert schema_report.failed_count == 0

        data_report, result_df = validate_data(group, cleaned_df, ValidationMode.NONE)
        assert data_report.failed_count == 0
        assert len(result_df) == 2


# ---------------------------------------------------------------------------
# Reference use case
# ---------------------------------------------------------------------------


class TestReferenceUseCase:
    """Validation with realistic data from the reference use case."""

    @staticmethod
    def _listing_features_group() -> FeatureGroup:
        """Build the listing_features definition from the reference use case."""
        return FeatureGroup(
            name="listing_features",
            storage_target=StorageTarget.OFFLINE,
            entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
            event_timestamp=EventTimestamp(name="event_timestamp", dtype=FeatureType.DATETIME),
            features=[
                Feature(name="net_area", dtype=FeatureType.INTEGER, expect=Expect().not_null().gt(0)),
                Feature(name="number_of_rooms", dtype=FeatureType.INTEGER, expect=Expect().not_null().gt(0)),
                Feature(name="build_year", dtype=FeatureType.INTEGER, expect=Expect().not_null().gte(1900).lte(2030)),
                Feature(name="sold_price", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)),
                Feature(name="town_id", dtype=FeatureType.INTEGER),
            ],
            join_keys=[JoinKey(field_name="town_id", referenced_group="town_market_features")],
            ingestion_validation=ValidationMode.ERROR,
            offline_retrieval_validation=ValidationMode.NONE,
            metadata=Metadata(
                description="Historical sold listing attributes and prices",
                owner="data-science-team",
            ),
        )

    @staticmethod
    def _listing_df() -> pd.DataFrame:
        """Build a realistic DataFrame for listing_features."""
        return pd.DataFrame(
            {
                "listing_id": [1001, 1002, 1003],
                "event_timestamp": pd.to_datetime(
                    [
                        "2024-03-15 11:00:00",
                        "2024-04-01 09:30:00",
                        "2024-03-18 14:30:00",
                    ]
                ),
                "net_area": [75, 120, 85],
                "number_of_rooms": [2, 4, 2],
                "build_year": [2020, 1995, 2002],
                "sold_price": [2250000.0, 3100000.0, 1050000.0],
                "town_id": [2, 5, 6],
            }
        )

    def test_reference_listing_schema_passes(self) -> None:
        """Reference use case listing data passes schema validation."""
        group = self._listing_features_group()
        df = self._listing_df()

        report, cleaned = validate_schema(group, df)
        assert report.failed_count == 0
        assert len(cleaned) == 3

    def test_reference_listing_data_passes(self) -> None:
        """Reference use case listing data passes data validation in ERROR mode."""
        group = self._listing_features_group()
        df = self._listing_df()

        _, cleaned = validate_schema(group, df)
        report, result = validate_data(group, cleaned, ValidationMode.ERROR)
        assert report.failed_count == 0
        assert len(result) == 3

    def test_reference_listing_bad_data_detected(self) -> None:
        """Injecting bad data into reference use case is caught."""
        group = self._listing_features_group()
        df = self._listing_df()
        # Inject invalid values
        df.loc[0, "net_area"] = -10  # fails gt(0)
        df.loc[1, "build_year"] = 1800  # fails gte(1900)

        _, cleaned = validate_schema(group, df)
        with pytest.raises(DataValidationError) as exc_info:
            validate_data(group, cleaned, ValidationMode.ERROR)

        report = exc_info.value.report
        assert report is not None
        assert report.failed_count == 2
        fields = {f.field for f in report.failures}
        assert "net_area" in fields
        assert "build_year" in fields

    def test_reference_listing_filter_mode(self) -> None:
        """FILTER mode on reference data excludes bad rows."""
        group = self._listing_features_group()
        df = self._listing_df()
        df.loc[0, "sold_price"] = -100.0  # fails gt(0)

        _, cleaned = validate_schema(group, df)
        report, filtered = validate_data(group, cleaned, ValidationMode.FILTER)

        assert report.failed_count == 1
        assert len(filtered) == 2
        assert 1001 not in filtered["listing_id"].values
