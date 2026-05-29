"""Unit tests for FeatureStore.get_historical_features() — parameter validation paths."""

from __future__ import annotations

import datetime
from pathlib import Path

import pyarrow as pa
import pytest

from kitefs.errors import FeatureGroupNotFoundError, RetrievalParameterError
from kitefs.providers.local.offline_store import LocalOfflineStore
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.tmp_store import make_initialized_project

_UTC = datetime.UTC

# Definition source files used to set up a project with listing_features.
# listing_features has a join key referencing town_market_features, so both
# definitions must be present for apply() to pass cross-definition validation.

_TOWN_MARKET_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[
        Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT),
    ],
    ingestion_validation=ValidationMode.NONE,
    metadata=Metadata(description="Town market", owner="team", tags={}),
)
"""

_LISTING_SRC = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup, FeatureType,
    JoinKey, Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="build_year", dtype=FeatureType.INTEGER, expect=Expect().not_null().gte(1900).lte(2030)),
        Feature(name="net_area", dtype=FeatureType.INTEGER, expect=Expect().not_null().gt(0)),
        Feature(name="number_of_rooms", dtype=FeatureType.INTEGER, expect=Expect().not_null().gt(0)),
        Feature(name="sold_price", dtype=FeatureType.FLOAT, expect=Expect().not_null().gt(0)),
    ],
    join_keys=[
        JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features"),
    ],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(description="Listing features", owner="team", tags={}),
)
"""


def _setup_project(tmp_path: Path) -> Path:
    """Scaffold, write both definitions, apply, and return the project root."""
    make_initialized_project(tmp_path)
    defs_dir = tmp_path / "feature_store" / "definitions"
    (defs_dir / "town_market_features.py").write_text(_TOWN_MARKET_SRC, encoding="utf-8")
    (defs_dir / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
    return tmp_path


def _stub_empty_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch LocalOfflineStore.read to return an empty table."""

    def _empty_read(
        self: LocalOfflineStore,
        feature_group: str,
        *,
        event_timestamp_column: str,
        schema: pa.Schema,
        timestamp_filter: object = None,
    ) -> pa.Table:
        return schema.empty_table()

    monkeypatch.setattr(LocalOfflineStore, "read", _empty_read)


class TestSelectValidation:
    """get_historical_features() raises RetrievalParameterError for invalid select."""

    def test_missing_select_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Omitting select raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(from_="listing_features")

    def test_bare_wildcard_string_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Passing select='*' (bare string) raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(from_="listing_features", select="*")  # type: ignore[arg-type]

    def test_mixed_wildcard_list_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """select=['*', 'net_area'] (mixed wildcard) raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(from_="listing_features", select=["*", "net_area"])

    def test_dict_select_without_join_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dict-shaped select without join raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(from_="listing_features", select={"listing_features": ["net_area"]})  # type: ignore[arg-type]

    def test_empty_select_list_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty select list raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(from_="listing_features", select=[])

    def test_unknown_feature_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Selecting an undeclared feature name raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(from_="listing_features", select=["city_name"])

    def test_unknown_feature_error_contains_name_and_feature_word(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown feature error message includes the field name and the word 'feature'."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError) as exc_info:
            FeatureStore().get_historical_features(from_="listing_features", select=["city_name"])

        msg = str(exc_info.value)
        assert "city_name" in msg
        assert "feature" in msg

    def test_join_provided_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Providing join= raises RetrievalParameterError (not supported in Feature 8)."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(
                from_="listing_features",
                select=["net_area"],
                join=["town_market_features"],
            )

    def test_unknown_group_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Retrieving from an unregistered group raises FeatureGroupNotFoundError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(FeatureGroupNotFoundError):
            FeatureStore().get_historical_features(from_="nonexistent_group", select=["col"])


class TestWhereValidation:
    """get_historical_features() raises RetrievalParameterError for invalid where."""

    def test_filter_on_non_timestamp_field_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Filtering on a non-event-timestamp field raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(
                from_="listing_features",
                select=["net_area"],
                where={"town_id": {"gte": datetime.datetime(2024, 1, 1, tzinfo=_UTC)}},
            )

    def test_non_timestamp_filter_error_contains_field_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The non-timestamp filter error message includes the offending field name."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError) as exc_info:
            FeatureStore().get_historical_features(
                from_="listing_features",
                select=["net_area"],
                where={"town_id": {"gte": datetime.datetime(2024, 1, 1, tzinfo=_UTC)}},
            )

        assert "town_id" in str(exc_info.value)

    def test_unsupported_operator_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Using an unsupported operator in where raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(
                from_="listing_features",
                select=["net_area"],
                where={"sold_at": {"eq": datetime.datetime(2024, 1, 1, tzinfo=_UTC)}},
            )

    def test_non_datetime_where_value_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-datetime value in where raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_empty_read(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_historical_features(
                from_="listing_features",
                select=["net_area"],
                where={"sold_at": {"gte": 1}},  # type: ignore[dict-item]
            )
