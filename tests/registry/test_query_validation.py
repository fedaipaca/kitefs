"""Tests for RegistryManager.validate_query_params — query parameter validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from helpers import MINIMAL_DEF, setup_manager, write_definition

from kitefs.exceptions import (
    FeatureGroupNotFoundError,
    JoinError,
    RetrievalError,
)

# ---------------------------------------------------------------------------
# Fixture: manager with a registered group whose event_timestamp.name = "ts"
# ---------------------------------------------------------------------------


def _setup_with_group(tmp_path, *, name: str = "test_group") -> RegistryManager:  # type: ignore[name-defined]  # noqa: F821
    """Create a RegistryManager with a single registered group."""
    manager = setup_manager(tmp_path)
    write_definition(
        manager._definitions_path,
        f"{name}.py",
        MINIMAL_DEF.format(varname="group", name=name),
    )
    manager.apply()
    return manager


# ---------------------------------------------------------------------------
# Group lookup
# ---------------------------------------------------------------------------


class TestGroupLookup:
    """validate_query_params raises FeatureGroupNotFoundError for unknown groups."""

    def test_unknown_group_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Unknown from_ group raises FeatureGroupNotFoundError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(FeatureGroupNotFoundError, match="no_such_group"):
            manager.validate_query_params(
                from_="no_such_group",
                select="*",
                where=None,
                join=None,
                method="get_historical_features",
            )

    def test_known_group_passes(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Known group does not raise."""
        manager = _setup_with_group(tmp_path)

        # Should not raise
        manager.validate_query_params(
            from_="test_group",
            select="*",
            where=None,
            join=None,
            method="get_historical_features",
        )


# ---------------------------------------------------------------------------
# Join rejection (no join support path)
# ---------------------------------------------------------------------------


class TestJoinRejection:
    """Non-empty join raises JoinError in the no-join path."""

    def test_non_empty_join_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Non-empty join list raises JoinError with future-release message."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(JoinError, match="Join support will be available"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where=None,
                join=["other_group"],
                method="get_historical_features",
            )

    def test_empty_join_passes(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Empty join list (or None) does not raise."""
        manager = _setup_with_group(tmp_path)

        manager.validate_query_params(
            from_="test_group", select="*", where=None, join=None, method="get_historical_features"
        )
        manager.validate_query_params(
            from_="test_group", select="*", where=None, join=[], method="get_historical_features"
        )


# ---------------------------------------------------------------------------
# Select validation
# ---------------------------------------------------------------------------


class TestSelectValidation:
    """select parameter validation for the no-join path."""

    def test_star_select_passes(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """select='*' is valid."""
        manager = _setup_with_group(tmp_path)

        manager.validate_query_params(
            from_="test_group", select="*", where=None, join=None, method="get_historical_features"
        )

    def test_valid_feature_list_passes(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """select=['value'] is valid (test_group has feature 'value')."""
        manager = _setup_with_group(tmp_path)

        manager.validate_query_params(
            from_="test_group", select=["value"], where=None, join=None, method="get_historical_features"
        )

    def test_empty_list_passes(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """select=[] is valid — returns structural columns only."""
        manager = _setup_with_group(tmp_path)

        manager.validate_query_params(
            from_="test_group", select=[], where=None, join=None, method="get_historical_features"
        )

    def test_unknown_feature_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """select with unknown feature name raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match=r"Unknown feature.*no_such_feature"):
            manager.validate_query_params(
                from_="test_group",
                select=["value", "no_such_feature"],
                where=None,
                join=None,
                method="get_historical_features",
            )

    def test_dict_select_without_join_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Dict-style select without join raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match=r"Dict-style.*requires.*join"):
            manager.validate_query_params(
                from_="test_group",
                select={"test_group": "*"},
                where=None,
                join=None,
                method="get_historical_features",
            )

    def test_non_star_string_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """String select that is not '*' raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Invalid select value"):
            manager.validate_query_params(
                from_="test_group",
                select="value",
                where=None,
                join=None,
                method="get_historical_features",
            )


# ---------------------------------------------------------------------------
# Where validation
# ---------------------------------------------------------------------------


class TestWhereValidation:
    """where parameter validation for get_historical_features."""

    def test_none_where_passes(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """where=None is valid."""
        manager = _setup_with_group(tmp_path)

        manager.validate_query_params(
            from_="test_group", select="*", where=None, join=None, method="get_historical_features"
        )

    def test_valid_where_datetime_passes(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """where with datetime values and valid operators passes."""
        manager = _setup_with_group(tmp_path)

        manager.validate_query_params(
            from_="test_group",
            select="*",
            where={"event_timestamp": {"gte": datetime(2024, 1, 1), "lte": datetime(2024, 12, 31)}},
            join=None,
            method="get_historical_features",
        )

    def test_valid_where_pd_timestamp_passes(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """where with pd.Timestamp values passes."""
        manager = _setup_with_group(tmp_path)

        manager.validate_query_params(
            from_="test_group",
            select="*",
            where={"event_timestamp": {"gte": pd.Timestamp("2024-01-01")}},
            join=None,
            method="get_historical_features",
        )

    def test_physical_column_name_rejected(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Using physical column name 'ts' instead of alias 'event_timestamp' raises."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Unsupported where field 'ts'"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where={"ts": {"gte": datetime(2024, 1, 1)}},
                join=None,
                method="get_historical_features",
            )

    def test_unsupported_operator_rejected(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Unsupported operator 'eq' raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Unsupported where operator 'eq'"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where={"event_timestamp": {"eq": datetime(2024, 1, 1)}},
                join=None,
                method="get_historical_features",
            )

    def test_string_value_rejected(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """String values for event_timestamp raise RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Invalid where value type 'str'"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where={"event_timestamp": {"gte": "2024-01-01"}},
                join=None,
                method="get_historical_features",
            )

    def test_int_value_rejected(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Integer values for event_timestamp raise RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Invalid where value type 'int'"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where={"event_timestamp": {"gte": 20240101}},
                join=None,
                method="get_historical_features",
            )


# ---------------------------------------------------------------------------
# Method dispatch
# ---------------------------------------------------------------------------


class TestMethodDispatch:
    """validate_query_params dispatches by method name."""

    def test_get_online_features_not_implemented(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """get_online_features method raises NotImplementedError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(NotImplementedError, match="get_online_features"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where=None,
                join=None,
                method="get_online_features",
            )

    def test_unknown_method_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """Unknown method string raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Unknown validation method"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where=None,
                join=None,
                method="bogus_method",
            )


# ---------------------------------------------------------------------------
# Select — non-string elements
# ---------------------------------------------------------------------------


class TestSelectNonStringElements:
    """Non-string elements in select list raise RetrievalError."""

    def test_integer_in_select_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """select=[1] raises RetrievalError with actionable message."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="non-string"):
            manager.validate_query_params(
                from_="test_group",
                select=[1],  # type: ignore[list-item]
                where=None,
                join=None,
                method="get_historical_features",
            )

    def test_mixed_types_in_select_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """select=['value', 1] raises RetrievalError for the non-string element."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="non-string"):
            manager.validate_query_params(
                from_="test_group",
                select=["value", 1],  # type: ignore[list-item]
                where=None,
                join=None,
                method="get_historical_features",
            )

    def test_none_element_in_select_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """select=[None] raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="non-string"):
            manager.validate_query_params(
                from_="test_group",
                select=[None],  # type: ignore[list-item]
                where=None,
                join=None,
                method="get_historical_features",
            )


# ---------------------------------------------------------------------------
# Where — non-dict top-level shape
# ---------------------------------------------------------------------------


class TestWhereNonDictShape:
    """Non-dict where top-level raises RetrievalError instead of crashing."""

    def test_list_where_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """where=[] raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Invalid where type 'list'"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where=[],  # type: ignore[arg-type]
                join=None,
                method="get_historical_features",
            )

    def test_string_where_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """where='bad' raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Invalid where type 'str'"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where="bad",  # type: ignore[arg-type]
                join=None,
                method="get_historical_features",
            )

    def test_int_where_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """where=1 raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="Invalid where type 'int'"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where=1,  # type: ignore[arg-type]
                join=None,
                method="get_historical_features",
            )


# ---------------------------------------------------------------------------
# Where — timezone-aware and NaT values
# ---------------------------------------------------------------------------


class TestWhereTimezoneEnforcement:
    """Timezone-aware and NaT values in where raise RetrievalError."""

    def test_tz_aware_datetime_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """datetime with tzinfo raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="timezone-naive"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where={"event_timestamp": {"gte": datetime(2024, 1, 1, tzinfo=UTC)}},
                join=None,
                method="get_historical_features",
            )

    def test_tz_aware_pd_timestamp_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """pd.Timestamp with tz raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="timezone-naive"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where={"event_timestamp": {"gte": pd.Timestamp("2024-01-01", tz="UTC")}},
                join=None,
                method="get_historical_features",
            )

    def test_nat_raises(self, tmp_path: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
        """pd.NaT as a where value raises RetrievalError."""
        manager = _setup_with_group(tmp_path)

        with pytest.raises(RetrievalError, match="NaT"):
            manager.validate_query_params(
                from_="test_group",
                select="*",
                where={"event_timestamp": {"gte": pd.NaT}},
                join=None,
                method="get_historical_features",
            )
