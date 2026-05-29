"""Unit tests for the offline store manager: prepare_ingestion_table()."""

from __future__ import annotations

import datetime

import pandas as pd
import pyarrow as pa

from kitefs.offline_store import prepare_ingestion_table
from kitefs.sdk.results import FeatureGroupDescription
from tests.fixtures.definitions import build_town_market_features
from tests.helpers.dataframes import town_market_frame

_UTC = datetime.UTC
_TS_FEB = datetime.datetime(2024, 2, 1, tzinfo=_UTC)


def _description() -> FeatureGroupDescription:
    """Return a FeatureGroupDescription for the town_market_features group."""
    from datetime import datetime

    from kitefs.registry.parser import describe_feature_group
    from kitefs.registry.serializer import build_registry_document

    groups = [build_town_market_features()]
    doc = build_registry_document(groups, prior_document={"feature_groups": {}}, now=datetime.now(_UTC))
    return describe_feature_group(doc, "town_market_features")


def _valid_frame(n: int = 2) -> pd.DataFrame:
    return town_market_frame(
        [
            {"town_id": i, "avg_price_per_sqm": float(20000 + i * 100), "event_timestamp": _TS_FEB}
            for i in range(1, n + 1)
        ]
    )


class TestPrepareIngestionTable:
    """prepare_ingestion_table() produces correctly typed PyArrow Tables."""

    def test_returns_pyarrow_table(self) -> None:
        """Returns a pa.Table instance."""
        desc = _description()
        frame = _valid_frame()

        result = prepare_ingestion_table(desc, frame)

        assert isinstance(result, pa.Table)

    def test_column_count_matches_declaration(self) -> None:
        """Output has exactly the declared columns (entity key + event_ts + features)."""
        desc = _description()
        frame = _valid_frame()

        result = prepare_ingestion_table(desc, frame)

        # town_id, event_timestamp, avg_price_per_sqm
        assert len(result.schema) == 3

    def test_extra_columns_are_dropped(self) -> None:
        """Extra columns not in the declaration are silently dropped."""
        desc = _description()
        frame = _valid_frame()
        frame = frame.assign(extra_col="noise")

        result = prepare_ingestion_table(desc, frame)

        assert "extra_col" not in result.schema.names

    def test_stable_column_order(self) -> None:
        """Columns appear in entity_key → event_timestamp → features order."""
        desc = _description()
        frame = _valid_frame()

        result = prepare_ingestion_table(desc, frame)

        assert result.schema.names == ["town_id", "event_timestamp", "avg_price_per_sqm"]

    def test_integer_column_type(self) -> None:
        """entity_key INTEGER maps to pa.int64()."""
        desc = _description()
        frame = _valid_frame()

        result = prepare_ingestion_table(desc, frame)

        assert result.schema.field("town_id").type == pa.int64()

    def test_float_column_type(self) -> None:
        """FLOAT feature maps to pa.float64()."""
        desc = _description()
        frame = _valid_frame()

        result = prepare_ingestion_table(desc, frame)

        assert result.schema.field("avg_price_per_sqm").type == pa.float64()

    def test_datetime_column_type(self) -> None:
        """event_timestamp DATETIME maps to pa.timestamp('us') (naive, no tz)."""
        desc = _description()
        frame = _valid_frame()

        result = prepare_ingestion_table(desc, frame)

        ts_type = result.schema.field("event_timestamp").type
        assert ts_type == pa.timestamp("us")

    def test_utc_aware_datetime_stripped(self) -> None:
        """UTC-aware pandas datetimes are stored as naive microsecond timestamps."""
        desc = _description()
        frame = _valid_frame()
        # Ensure the column is UTC-aware pandas dtype.
        frame["event_timestamp"] = pd.to_datetime(frame["event_timestamp"], utc=True)

        result = prepare_ingestion_table(desc, frame)

        ts_type = result.schema.field("event_timestamp").type
        assert ts_type == pa.timestamp("us")
        # The value should equal the original moment (stripped of tz).
        ts_val = result.column("event_timestamp")[0].as_py()
        assert ts_val == datetime.datetime(2024, 2, 1, 0, 0, 0)

    def test_row_count_preserved(self) -> None:
        """Output row count equals input row count."""
        desc = _description()
        frame = _valid_frame(5)

        result = prepare_ingestion_table(desc, frame)

        assert len(result) == 5
