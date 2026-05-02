"""Tests for FeatureStore.get_historical_features — single group, no join."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from helpers import setup_project

from kitefs.exceptions import (
    DataValidationError,
    FeatureGroupNotFoundError,
    JoinError,
    RetrievalError,
)
from kitefs.feature_store import FeatureStore

# ---------------------------------------------------------------------------
# Definition templates
# ---------------------------------------------------------------------------

# Minimal group: entity_key="id", event_timestamp="ts", feature="value"
_SIMPLE_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, StorageTarget,
)

simple_group = FeatureGroup(
    name="simple_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[Feature(name="value", dtype=FeatureType.FLOAT)],
)
"""

# ERROR mode retrieval validation, NONE ingestion to allow bad data in
_ERROR_RETRIEVAL_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, StorageTarget, ValidationMode,
)

error_group = FeatureGroup(
    name="error_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[
        Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)),
    ],
    ingestion_validation=ValidationMode.NONE,
    offline_retrieval_validation=ValidationMode.ERROR,
)
"""

# FILTER mode retrieval validation, NONE ingestion to allow bad data in
_FILTER_RETRIEVAL_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, StorageTarget, ValidationMode,
)

filter_group = FeatureGroup(
    name="filter_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[
        Feature(name="value", dtype=FeatureType.FLOAT, expect=Expect().gt(0)),
    ],
    ingestion_validation=ValidationMode.NONE,
    offline_retrieval_validation=ValidationMode.FILTER,
)
"""

# NONE mode (default) with multiple features and a join key.
# Both groups must be registered so cross-group validation passes.
_MULTI_FEATURE_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, JoinKey, StorageTarget,
)

multi_group = FeatureGroup(
    name="multi_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[
        Feature(name="area", dtype=FeatureType.INTEGER),
        Feature(name="price", dtype=FeatureType.FLOAT),
        Feature(name="town_id", dtype=FeatureType.INTEGER),
    ],
    join_keys=[JoinKey(field_name="town_id", referenced_group="ref_group")],
)
"""

_REF_GROUP_DEF = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, StorageTarget,
)

ref_group = FeatureGroup(
    name="ref_group",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[Feature(name="metric", dtype=FeatureType.FLOAT)],
)
"""


# ---------------------------------------------------------------------------
# DataFrame builders
# ---------------------------------------------------------------------------


def _simple_df(timestamps: list[str] | None = None) -> pd.DataFrame:
    """Build a DataFrame matching simple_group schema."""
    if timestamps is None:
        timestamps = ["2024-03-15", "2024-04-10", "2024-06-20"]
    n = len(timestamps)
    return pd.DataFrame(
        {
            "id": list(range(1, n + 1)),
            "ts": pd.to_datetime(timestamps),
            "value": [100.0 * i for i in range(1, n + 1)],
        }
    )


def _multi_df() -> pd.DataFrame:
    """Build a DataFrame matching multi_group schema."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "ts": pd.to_datetime(["2024-03-15", "2024-04-10", "2024-06-20"]),
            "area": [80, 120, 95],
            "price": [500000.0, 800000.0, 650000.0],
            "town_id": [10, 20, 10],
        }
    )


def _error_df() -> pd.DataFrame:
    """Build a DataFrame for error_group with some invalid values (value <= 0)."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "ts": pd.to_datetime(["2024-03-15", "2024-04-10", "2024-06-20"]),
            "value": [-10.0, 200.0, 300.0],
        }
    )


def _filter_df() -> pd.DataFrame:
    """Build a DataFrame for filter_group with some invalid values."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "ts": pd.to_datetime(["2024-03-15", "2024-04-10", "2024-06-20"]),
            "value": [-10.0, 200.0, 0.0],
        }
    )


# ---------------------------------------------------------------------------
# Helper: set up project, apply, ingest, return store
# ---------------------------------------------------------------------------


def _store_with_data(
    tmp_path,
    definitions: dict[str, str],
    ingest_map: dict[str, pd.DataFrame],
) -> FeatureStore:
    """Set up a project, apply definitions, ingest data, return FeatureStore."""
    setup_project(tmp_path, definitions=definitions)
    store = FeatureStore(project_root=tmp_path)
    store.apply()
    for group_name, df in ingest_map.items():
        store.ingest(group_name, df)
    return store


# ===========================================================================
# Test classes
# ===========================================================================


class TestSelectStar:
    """select='*' returns all columns."""

    def test_star_returns_all_columns(self, tmp_path) -> None:
        """select='*' returns entity key, event timestamp, and all features."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        result = store.get_historical_features(from_="simple_group", select="*")

        assert list(result.columns) == ["id", "ts", "value"]
        assert len(result) == 3

    def test_star_returns_all_features_including_join_key(self, tmp_path) -> None:
        """select='*' includes join key fields as features."""
        store = _store_with_data(
            tmp_path,
            {"multi.py": _MULTI_FEATURE_DEF, "ref.py": _REF_GROUP_DEF},
            {"multi_group": _multi_df()},
        )

        result = store.get_historical_features(from_="multi_group", select="*")

        assert "town_id" in result.columns
        assert "area" in result.columns
        assert "price" in result.columns
        assert len(result) == 3


class TestSelectList:
    """select as list returns only structural + selected features."""

    def test_list_select_subset(self, tmp_path) -> None:
        """select=['area'] returns only entity key + event timestamp + area."""
        store = _store_with_data(
            tmp_path,
            {"multi.py": _MULTI_FEATURE_DEF, "ref.py": _REF_GROUP_DEF},
            {"multi_group": _multi_df()},
        )

        result = store.get_historical_features(from_="multi_group", select=["area"])

        assert list(result.columns) == ["id", "ts", "area"]
        assert len(result) == 3

    def test_list_select_multiple(self, tmp_path) -> None:
        """select=['area', 'price'] returns both features + structural."""
        store = _store_with_data(
            tmp_path,
            {"multi.py": _MULTI_FEATURE_DEF, "ref.py": _REF_GROUP_DEF},
            {"multi_group": _multi_df()},
        )

        result = store.get_historical_features(from_="multi_group", select=["area", "price"])

        assert "id" in result.columns
        assert "ts" in result.columns
        assert "area" in result.columns
        assert "price" in result.columns
        assert "town_id" not in result.columns

    def test_empty_list_returns_structural_only(self, tmp_path) -> None:
        """select=[] returns only structural columns."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        result = store.get_historical_features(from_="simple_group", select=[])

        assert list(result.columns) == ["id", "ts"]
        assert len(result) == 3


class TestJoinKeyExclusion:
    """No-join select does not force-include join keys."""

    def test_join_key_not_included_unless_selected(self, tmp_path) -> None:
        """select=['area'] on a group with join_keys does not include town_id."""
        store = _store_with_data(
            tmp_path,
            {"multi.py": _MULTI_FEATURE_DEF, "ref.py": _REF_GROUP_DEF},
            {"multi_group": _multi_df()},
        )

        result = store.get_historical_features(from_="multi_group", select=["area"])

        assert "town_id" not in result.columns
        assert list(result.columns) == ["id", "ts", "area"]

    def test_join_key_included_when_explicitly_selected(self, tmp_path) -> None:
        """select=['area', 'town_id'] includes town_id."""
        store = _store_with_data(
            tmp_path,
            {"multi.py": _MULTI_FEATURE_DEF, "ref.py": _REF_GROUP_DEF},
            {"multi_group": _multi_df()},
        )

        result = store.get_historical_features(from_="multi_group", select=["area", "town_id"])

        assert "town_id" in result.columns


class TestWhereFiltering:
    """where parameter filters data correctly."""

    def test_gte_lte_filter(self, tmp_path) -> None:
        """where with gte and lte narrows results correctly."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        result = store.get_historical_features(
            from_="simple_group",
            select="*",
            where={"event_timestamp": {"gte": datetime(2024, 4, 1), "lte": datetime(2024, 5, 1)}},
        )

        assert len(result) == 1
        assert result["id"].iloc[0] == 2

    def test_gt_filter(self, tmp_path) -> None:
        """where with gt excludes boundary."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df(["2024-03-15", "2024-04-10", "2024-06-20"])},
        )

        result = store.get_historical_features(
            from_="simple_group",
            select="*",
            where={"event_timestamp": {"gt": datetime(2024, 4, 10)}},
        )

        assert len(result) == 1
        assert result["id"].iloc[0] == 3

    def test_no_where_returns_all(self, tmp_path) -> None:
        """where=None returns all records."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        result = store.get_historical_features(from_="simple_group", select="*")

        assert len(result) == 3


class TestAliasResolution:
    """Event timestamp alias resolution in where clause."""

    def test_alias_works_with_physical_ts_column(self, tmp_path) -> None:
        """where={'event_timestamp': {...}} works when physical column is 'ts'."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        # Physical column is "ts", but where uses logical alias "event_timestamp"
        result = store.get_historical_features(
            from_="simple_group",
            select="*",
            where={"event_timestamp": {"gte": datetime(2024, 4, 1)}},
        )

        assert len(result) == 2

    def test_physical_name_in_where_rejected(self, tmp_path) -> None:
        """where={'ts': {...}} rejected with RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="Unsupported where field 'ts'"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where={"ts": {"gte": datetime(2024, 4, 1)}},
            )


class TestEmptyResult:
    """Empty results return a DataFrame with correct columns."""

    def test_no_data_ingested_returns_empty_with_correct_columns(self, tmp_path) -> None:
        """No data ingested → empty DataFrame with correct output columns."""
        setup_project(tmp_path, definitions={"simple.py": _SIMPLE_DEF})
        store = FeatureStore(project_root=tmp_path)
        store.apply()

        result = store.get_historical_features(from_="simple_group", select="*")

        assert result.empty
        assert list(result.columns) == ["id", "ts", "value"]

    def test_where_filters_everything_returns_empty_with_columns(self, tmp_path) -> None:
        """where that excludes all records → empty DataFrame with correct columns."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        result = store.get_historical_features(
            from_="simple_group",
            select=["value"],
            where={"event_timestamp": {"gte": datetime(2025, 1, 1)}},
        )

        assert result.empty
        assert list(result.columns) == ["id", "ts", "value"]

    def test_empty_result_with_list_select(self, tmp_path) -> None:
        """Empty result with list select has the correct subset of columns."""
        setup_project(tmp_path, definitions={"multi.py": _MULTI_FEATURE_DEF, "ref.py": _REF_GROUP_DEF})
        store = FeatureStore(project_root=tmp_path)
        store.apply()

        result = store.get_historical_features(from_="multi_group", select=["area"])

        assert result.empty
        assert list(result.columns) == ["id", "ts", "area"]


class TestRetrievalValidationModes:
    """Retrieval-gate validation modes (ERROR, FILTER, NONE)."""

    def test_error_mode_raises_on_invalid_data(self, tmp_path) -> None:
        """ERROR mode with invalid data raises DataValidationError."""
        store = _store_with_data(
            tmp_path,
            {"error.py": _ERROR_RETRIEVAL_DEF},
            {"error_group": _error_df()},
        )

        with pytest.raises(DataValidationError):
            store.get_historical_features(from_="error_group", select="*")

    def test_filter_mode_excludes_failing_rows(self, tmp_path) -> None:
        """FILTER mode removes rows failing expectations."""
        store = _store_with_data(
            tmp_path,
            {"filter.py": _FILTER_RETRIEVAL_DEF},
            {"filter_group": _filter_df()},
        )

        result = store.get_historical_features(from_="filter_group", select="*")

        # value=-10 and value=0 fail gt(0), only value=200 passes
        assert len(result) == 1
        assert result["value"].iloc[0] == 200.0

    def test_none_mode_passes_all_through(self, tmp_path) -> None:
        """NONE mode (default) passes all data through without validation."""
        # simple_group has offline_retrieval_validation=NONE (default)
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        result = store.get_historical_features(from_="simple_group", select="*")

        assert len(result) == 3

    def test_filter_mode_all_filtered_returns_empty(self, tmp_path) -> None:
        """FILTER mode with all rows failing returns empty DataFrame with columns."""
        all_bad_df = pd.DataFrame(
            {
                "id": [1, 2],
                "ts": pd.to_datetime(["2024-03-15", "2024-04-10"]),
                "value": [-10.0, 0.0],
            }
        )
        store = _store_with_data(
            tmp_path,
            {"filter.py": _FILTER_RETRIEVAL_DEF},
            {"filter_group": all_bad_df},
        )

        result = store.get_historical_features(from_="filter_group", select="*")

        assert result.empty
        assert list(result.columns) == ["id", "ts", "value"]


class TestErrorPaths:
    """Error paths for get_historical_features."""

    def test_unknown_group_raises(self, tmp_path) -> None:
        """Unknown from_ raises FeatureGroupNotFoundError."""
        setup_project(tmp_path, definitions={"simple.py": _SIMPLE_DEF})
        store = FeatureStore(project_root=tmp_path)
        store.apply()

        with pytest.raises(FeatureGroupNotFoundError, match="no_such_group"):
            store.get_historical_features(from_="no_such_group", select="*")

    def test_invalid_select_feature_raises(self, tmp_path) -> None:
        """select with non-existent feature raises RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match=r"Unknown feature.*nonexistent"):
            store.get_historical_features(from_="simple_group", select=["nonexistent"])

    def test_dict_select_without_join_raises(self, tmp_path) -> None:
        """Dict-style select without join raises RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="Dict-style"):
            store.get_historical_features(from_="simple_group", select={"simple_group": "*"})

    def test_join_raises_join_error(self, tmp_path) -> None:
        """Non-empty join raises JoinError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(JoinError, match="Join support will be available"):
            store.get_historical_features(from_="simple_group", select="*", join=["other_group"])

    def test_where_string_value_raises(self, tmp_path) -> None:
        """String values in where raise RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="Invalid where value type 'str'"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where={"event_timestamp": {"gte": "2024-01-01"}},
            )

    def test_where_int_value_raises(self, tmp_path) -> None:
        """Integer values in where raise RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="Invalid where value type 'int'"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where={"event_timestamp": {"gte": 20240101}},
            )

    def test_where_unsupported_operator_raises(self, tmp_path) -> None:
        """Unsupported operator in where raises RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="Unsupported where operator 'eq'"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where={"event_timestamp": {"eq": datetime(2024, 1, 1)}},
            )


class TestDataCorrectness:
    """Verify that returned data values are correct."""

    def test_values_match_ingested_data(self, tmp_path) -> None:
        """Returned values match what was ingested."""
        df = _simple_df(["2024-03-15"])
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": df},
        )

        result = store.get_historical_features(from_="simple_group", select="*")

        assert len(result) == 1
        assert result["id"].iloc[0] == 1
        assert result["value"].iloc[0] == 100.0

    def test_where_pd_timestamp_works(self, tmp_path) -> None:
        """pd.Timestamp values in where work correctly."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        result = store.get_historical_features(
            from_="simple_group",
            select="*",
            where={"event_timestamp": {"gte": pd.Timestamp("2024-04-01")}},
        )

        assert len(result) == 2


# ---------------------------------------------------------------------------
# Malformed input — robustness regressions
# ---------------------------------------------------------------------------


class TestMalformedSelect:
    """Non-string elements in select and other malformed input via SDK."""

    def test_non_string_select_element_raises(self, tmp_path) -> None:
        """select=[1] at SDK level raises RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="non-string"):
            store.get_historical_features(from_="simple_group", select=[1])  # type: ignore[list-item]

    def test_mixed_select_elements_raises(self, tmp_path) -> None:
        """select=['value', 1] at SDK level raises RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="non-string"):
            store.get_historical_features(from_="simple_group", select=["value", 1])  # type: ignore[list-item]


class TestMalformedWhere:
    """Non-dict where and other malformed input via SDK."""

    def test_list_where_raises(self, tmp_path) -> None:
        """where=[] at SDK level raises RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="Invalid where type"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where=[],  # type: ignore[arg-type]
            )

    def test_string_where_raises(self, tmp_path) -> None:
        """where='bad' at SDK level raises RetrievalError."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="Invalid where type"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where="bad",  # type: ignore[arg-type]
            )


class TestTimezoneAwareWhereSDK:
    """Timezone-aware where values at SDK level raise RetrievalError."""

    def test_tz_aware_datetime_raises(self, tmp_path) -> None:
        """datetime with tzinfo raises RetrievalError at SDK level."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="timezone-naive"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where={"event_timestamp": {"gte": datetime(2024, 1, 1, tzinfo=UTC)}},
            )

    def test_tz_aware_pd_timestamp_raises(self, tmp_path) -> None:
        """pd.Timestamp with tz raises RetrievalError at SDK level."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="timezone-naive"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where={"event_timestamp": {"gte": pd.Timestamp("2024-01-01", tz="UTC")}},
            )

    def test_nat_where_raises(self, tmp_path) -> None:
        """pd.NaT as a where value raises RetrievalError at SDK level."""
        store = _store_with_data(
            tmp_path,
            {"simple.py": _SIMPLE_DEF},
            {"simple_group": _simple_df()},
        )

        with pytest.raises(RetrievalError, match="NaT"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where={"event_timestamp": {"gte": pd.NaT}},
            )

    def test_tz_aware_on_empty_store_still_raises(self, tmp_path) -> None:
        """Timezone-aware value on empty store raises — not silently succeeds."""
        setup_project(tmp_path, definitions={"simple.py": _SIMPLE_DEF})
        store = FeatureStore(project_root=tmp_path)
        store.apply()

        with pytest.raises(RetrievalError, match="timezone-naive"):
            store.get_historical_features(
                from_="simple_group",
                select="*",
                where={"event_timestamp": {"gte": datetime(2024, 1, 1, tzinfo=UTC)}},
            )


class TestRetrievalValidationContext:
    """DataValidationError from retrieval includes feature-group context."""

    def test_error_message_includes_group_name(self, tmp_path) -> None:
        """DataValidationError wraps the group name for debugging."""
        store = _store_with_data(
            tmp_path,
            {"error.py": _ERROR_RETRIEVAL_DEF},
            {"error_group": _error_df()},
        )

        with pytest.raises(DataValidationError, match="error_group"):
            store.get_historical_features(from_="error_group", select="*")

    def test_error_preserves_validation_report(self, tmp_path) -> None:
        """DataValidationError re-raised during retrieval carries the validation report."""
        store = _store_with_data(
            tmp_path,
            {"error.py": _ERROR_RETRIEVAL_DEF},
            {"error_group": _error_df()},
        )

        with pytest.raises(DataValidationError) as exc_info:
            store.get_historical_features(from_="error_group", select="*")

        assert exc_info.value.report is not None
        assert exc_info.value.report.failed_count > 0
