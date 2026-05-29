"""Unit tests for the shape check (_check_shape)."""

from __future__ import annotations

import pandas as pd
import pytest

from kitefs.enums import FeatureType, ValidationMode
from kitefs.errors import IngestionShapeError
from kitefs.sdk.results import FieldSpec, JoinKeySpec
from kitefs.validation import validate_dataframe
from tests.unit.validation.conftest import make_description


class TestMissingStructuralColumns:
    """validate_dataframe raises IngestionShapeError when a structural column is absent."""

    def test_missing_entity_key_raises(self) -> None:
        """A DataFrame lacking the entity key column raises IngestionShapeError."""
        desc = make_description(entity_key_name="town_id")
        frame = pd.DataFrame({"ts": pd.to_datetime(["2024-01-01"]), "value": [1.0]})

        with pytest.raises(IngestionShapeError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        assert "town_id" in str(exc_info.value)

    def test_missing_event_timestamp_raises(self) -> None:
        """A DataFrame lacking the event_timestamp column raises IngestionShapeError."""
        desc = make_description(event_timestamp_name="event_ts")
        frame = pd.DataFrame({"id": [1], "value": [1.0]})

        with pytest.raises(IngestionShapeError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        assert "event_ts" in str(exc_info.value)

    def test_missing_join_key_raises(self) -> None:
        """A DataFrame lacking a declared join key column raises IngestionShapeError."""
        desc = make_description(
            join_keys=[JoinKeySpec(name="town_id", dtype=FeatureType.INTEGER, referenced_group="other")]
        )
        frame = pd.DataFrame({"id": [1], "ts": pd.to_datetime(["2024-01-01"]), "value": [1.0]})

        with pytest.raises(IngestionShapeError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        assert "town_id" in str(exc_info.value)


class TestMissingFeatureColumns:
    """validate_dataframe raises IngestionShapeError when a feature column is absent."""

    def test_missing_feature_column_raises(self) -> None:
        """A DataFrame lacking a declared feature column raises IngestionShapeError."""
        desc = make_description(
            features=[FieldSpec(name="avg_price", dtype=FeatureType.FLOAT, description=None, expect=None)]
        )
        frame = pd.DataFrame({"id": [1], "ts": pd.to_datetime(["2024-01-01"])})

        with pytest.raises(IngestionShapeError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        assert "avg_price" in str(exc_info.value)

    def test_error_message_lists_all_missing(self) -> None:
        """IngestionShapeError message includes every missing column name."""
        desc = make_description(
            features=[
                FieldSpec(name="feat_a", dtype=FeatureType.FLOAT, description=None, expect=None),
                FieldSpec(name="feat_b", dtype=FeatureType.FLOAT, description=None, expect=None),
            ]
        )
        frame = pd.DataFrame({"id": [1], "ts": pd.to_datetime(["2024-01-01"])})

        with pytest.raises(IngestionShapeError) as exc_info:
            validate_dataframe(desc, frame, ValidationMode.ERROR, operation="ingestion")

        msg = str(exc_info.value)
        assert "feat_a" in msg
        assert "feat_b" in msg


class TestExtraColumnsIgnored:
    """validate_dataframe ignores columns not declared in the feature group."""

    def test_extra_column_does_not_raise(self) -> None:
        """A DataFrame with extra columns beyond the schema passes shape check."""
        desc = make_description()
        frame = pd.DataFrame(
            {
                "id": [1],
                "ts": pd.to_datetime(["2024-01-01"]),
                "value": [1.0],
                "extra_col": ["ignored"],
            }
        )

        # Should not raise IngestionShapeError (may raise for other reasons, but not shape)
        try:
            validate_dataframe(desc, frame, ValidationMode.NONE, operation="ingestion")
        except IngestionShapeError:
            pytest.fail("IngestionShapeError raised for extra column — should be ignored")
