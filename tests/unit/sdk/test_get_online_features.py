"""Unit tests for FeatureStore.get_online_features() — parameter validation paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kitefs.errors import (
    FeatureGroupNotFoundError,
    FeatureGroupNotMaterializableError,
    OnlineStoreReadError,
    RetrievalParameterError,
)
from kitefs.providers.local.online_store import LocalOnlineStore
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.tmp_store import make_initialized_project

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
    EntityKey, EventTimestamp, Feature, FeatureGroup, FeatureType,
    Metadata, StorageTarget, ValidationMode,
)

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[
        Feature(name="net_area", dtype=FeatureType.INTEGER),
    ],
    ingestion_validation=ValidationMode.NONE,
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


def _stub_online_get_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch LocalOnlineStore.get to fail if validation reaches storage."""

    def _fail_get(
        self: LocalOnlineStore,
        feature_group: str,
        entity_key_value: str | int,
        *,
        entity_key_column: str,
        select: list[str] | None,
    ) -> dict[str, Any]:
        raise AssertionError(f"get() should not be called for {feature_group}")

    monkeypatch.setattr(LocalOnlineStore, "get", _fail_get)


def _stub_online_get_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch LocalOnlineStore.get to return {} (miss)."""

    def _empty_get(
        self: LocalOnlineStore,
        feature_group: str,
        entity_key_value: str | int,
        *,
        entity_key_column: str,
        select: list[str] | None,
    ) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(LocalOnlineStore, "get", _empty_get)


class TestGroupValidation:
    """get_online_features() rejects unknown and OFFLINE groups."""

    def test_unknown_group_raises_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unregistered group name raises FeatureGroupNotFoundError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(FeatureGroupNotFoundError):
            FeatureStore().get_online_features(
                from_="nonexistent_group",
                select=["avg_price_per_sqm"],
                where={"town_id": {"eq": 1}},
            )

    def test_offline_group_raises_not_materializable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A group with storage_target=OFFLINE raises FeatureGroupNotMaterializableError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(FeatureGroupNotMaterializableError):
            FeatureStore().get_online_features(
                from_="listing_features",
                select=["net_area"],
                where={"listing_id": {"eq": 1}},
            )

    def test_offline_group_error_contains_group_name_and_offline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The error message contains the group name and 'OFFLINE'."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(FeatureGroupNotMaterializableError, match="listing_features"):
            FeatureStore().get_online_features(
                from_="listing_features",
                select=["net_area"],
                where={"listing_id": {"eq": 1}},
            )


class TestSelectValidation:
    """get_online_features() raises RetrievalParameterError for invalid select."""

    def test_missing_select_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Omitting select raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                where={"town_id": {"eq": 1}},
            )

    def test_bare_wildcard_string_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Passing select='*' (bare string) raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select="*",  # type: ignore[arg-type]
                where={"town_id": {"eq": 1}},
            )

    def test_empty_select_list_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty select list raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=[],
                where={"town_id": {"eq": 1}},
            )

    def test_dict_select_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dict-shaped select raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select={"town_market_features": ["avg_price_per_sqm"]},  # type: ignore[arg-type]
                where={"town_id": {"eq": 1}},
            )

    def test_mixed_wildcard_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """select=['*', 'avg_price_per_sqm'] (mixed wildcard) raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["*", "avg_price_per_sqm"],
                where={"town_id": {"eq": 1}},
            )

    def test_unknown_feature_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Selecting an undeclared feature name raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["undeclared_feature"],
                where={"town_id": {"eq": 1}},
            )


class TestWhereValidation:
    """get_online_features() raises RetrievalParameterError for invalid where."""

    def test_missing_where_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Omitting where raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
            )

    def test_non_dict_where_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Passing a non-dict where raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where="town_id=1",  # type: ignore[arg-type]
            )

    def test_multi_key_where_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """where with more than one key raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"town_id": {"eq": 1}, "extra": {"eq": 2}},
            )

    def test_wrong_field_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Filtering on a non-entity-key field raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"avg_price_per_sqm": {"eq": 24500.0}},
            )

    def test_wrong_field_error_contains_filter_field_and_entity_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Error message for wrong where field contains the bad field name and the entity key name."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError, match="avg_price_per_sqm"):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"avg_price_per_sqm": {"eq": 24500.0}},
            )

    def test_non_dict_operator_mapping_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Passing a non-dict operator mapping raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"town_id": 1},  # type: ignore[dict-item]
            )

    def test_unsupported_operator_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Passing an operator other than 'eq' raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"town_id": {"gt": 1}},
            )

    def test_extra_operators_alongside_eq_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Passing 'eq' plus additional operators raises RetrievalParameterError."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"town_id": {"eq": 1, "gt": 0}},
            )

    def test_bool_rejected_for_integer_entity_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """bool is rejected for an INTEGER entity key (bool is a subclass of int)."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"town_id": {"eq": True}},
            )

    def test_string_rejected_for_integer_entity_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A string value is rejected for an INTEGER entity key."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_failure(monkeypatch)

        with pytest.raises(RetrievalParameterError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"town_id": {"eq": "1"}},
            )


class TestProviderCall:
    """get_online_features() calls the provider with the correct arguments on a valid request."""

    def test_valid_request_returns_empty_dict_on_miss(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid request that misses returns {}."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_empty(monkeypatch)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 1}},
        )
        assert result == {}

    def test_wildcard_select_resolves_to_all_features(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """select=['*'] resolves without error and calls the provider."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        _stub_online_get_empty(monkeypatch)

        result = FeatureStore().get_online_features(
            from_="town_market_features",
            select=["*"],
            where={"town_id": {"eq": 1}},
        )
        assert result == {}

    def test_provider_called_with_structural_columns_first(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The provider receives output_columns = structural + selected, in that order."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()

        captured: dict[str, Any] = {}

        def _capture_get(
            self: LocalOnlineStore,
            feature_group: str,
            entity_key_value: str | int,
            *,
            entity_key_column: str,
            select: list[str] | None,
        ) -> dict[str, Any]:
            captured["feature_group"] = feature_group
            captured["entity_key_value"] = entity_key_value
            captured["entity_key_column"] = entity_key_column
            captured["select"] = select
            return {}

        monkeypatch.setattr(LocalOnlineStore, "get", _capture_get)

        FeatureStore().get_online_features(
            from_="town_market_features",
            select=["avg_price_per_sqm"],
            where={"town_id": {"eq": 42}},
        )

        assert captured["feature_group"] == "town_market_features"
        assert captured["entity_key_value"] == 42
        assert captured["entity_key_column"] == "town_id"
        # Structural columns (entity key, event timestamp) come before selected features.
        assert captured["select"] is not None
        assert captured["select"][0] == "town_id"
        assert captured["select"][1] == "event_timestamp"
        assert "avg_price_per_sqm" in captured["select"]

    def test_malformed_datetime_raises_online_store_read_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_online_features() raises OnlineStoreReadError when the online store has a malformed datetime."""
        _setup_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        FeatureStore().apply()
        monkeypatch.setattr(
            LocalOnlineStore,
            "get",
            lambda *a, **kw: {"town_id": 1, "event_timestamp": "not-a-date", "avg_price_per_sqm": 25000.0},
        )
        with pytest.raises(OnlineStoreReadError):
            FeatureStore().get_online_features(
                from_="town_market_features",
                select=["avg_price_per_sqm"],
                where={"town_id": {"eq": 1}},
            )
