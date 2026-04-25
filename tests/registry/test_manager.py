"""Tests for RegistryManager operations."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, make_local_config, setup_manager

from kitefs.definitions import StorageTarget, ValidationMode
from kitefs.exceptions import DefinitionError, FeatureGroupNotFoundError, ProviderError, RegistryError
from kitefs.providers.local import LocalProvider
from kitefs.registry import RegistryManager


class TestRegistryManagerApplySuccess:
    """Happy-path tests for RegistryManager.apply()."""

    def test_apply_single_group_returns_apply_result(self, tmp_path: Path) -> None:
        """apply() with one definition returns an ApplyResult with count 1."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "group.py").write_text(MINIMAL_DEF.format(varname="group", name="my_group"))

        result = manager.apply()

        assert result.group_count == 1
        assert result.registered_groups == ("my_group",)

    def test_apply_multiple_groups_returns_all(self, tmp_path: Path) -> None:
        """apply() with two definitions returns both group names."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "alpha.py").write_text(MINIMAL_DEF.format(varname="alpha", name="alpha"))
        (manager._definitions_path / "beta.py").write_text(MINIMAL_DEF.format(varname="beta", name="beta"))

        result = manager.apply()

        assert result.group_count == 2
        assert result.registered_groups == ("alpha", "beta")

    def test_apply_writes_registry_json(self, tmp_path: Path) -> None:
        """apply() persists the group to registry.json on disk."""
        config = make_local_config(tmp_path)
        config.storage_root.mkdir(parents=True, exist_ok=True)
        config.definitions_path.mkdir(parents=True, exist_ok=True)
        registry_path = config.storage_root / "registry.json"
        registry_path.write_text('{"version": "1.0", "feature_groups": {}}', encoding="utf-8")

        provider = LocalProvider(config)
        manager = RegistryManager(provider, config.definitions_path)
        (manager._definitions_path / "group.py").write_text(MINIMAL_DEF.format(varname="group", name="my_group"))
        manager.apply()

        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert data["version"] == "1.0"
        assert "my_group" in data["feature_groups"]

    def test_apply_version_field_is_1_0(self, tmp_path: Path) -> None:
        """Registry version is always 1.0 after apply."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        assert manager._registry["version"] == "1.0"

    def test_applied_at_is_valid_iso8601(self, tmp_path: Path) -> None:
        """applied_at is a parseable ISO 8601 datetime string."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        applied_at = manager._registry["feature_groups"]["g"]["applied_at"]
        # Must not raise — valid ISO 8601
        parsed = datetime.fromisoformat(applied_at)
        assert parsed is not None

    def test_last_materialized_at_null_for_new_group(self, tmp_path: Path) -> None:
        """A newly registered group has null last_materialized_at."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        assert manager._registry["feature_groups"]["g"]["last_materialized_at"] is None

    def test_last_materialized_at_preserved_on_reapply(self, tmp_path: Path) -> None:
        """Re-applying preserves the existing last_materialized_at value."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        # Simulate a materialization by manually setting the value in the registry file.
        registry_path = cast(LocalProvider, manager._provider)._registry_path
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data["feature_groups"]["g"]["last_materialized_at"] = "2025-06-01T12:00:00+00:00"
        registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Re-load and re-apply.
        config2 = make_local_config(tmp_path)
        provider2 = LocalProvider(config2)
        manager2 = RegistryManager(provider2, manager._definitions_path)
        manager2.apply()

        assert manager2._registry["feature_groups"]["g"]["last_materialized_at"] == "2025-06-01T12:00:00+00:00"

    def test_deleted_definition_vanishes_on_reapply(self, tmp_path: Path) -> None:
        """Groups whose definition file is removed no longer appear after re-apply."""
        manager = setup_manager(tmp_path)
        def_alpha = manager._definitions_path / "alpha.py"
        def_beta = manager._definitions_path / "beta.py"
        def_alpha.write_text(MINIMAL_DEF.format(varname="alpha", name="alpha"))
        def_beta.write_text(MINIMAL_DEF.format(varname="beta", name="beta"))
        manager.apply()

        assert manager.group_exists("alpha")
        assert manager.group_exists("beta")

        def_beta.unlink()
        manager.apply()

        assert manager.group_exists("alpha")
        assert not manager.group_exists("beta")

    def test_deterministic_json_output(self, tmp_path: Path) -> None:
        """Applying the same definitions twice produces identical JSON (exc. applied_at)."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()
        registry_path = cast(LocalProvider, manager._provider)._registry_path
        first = json.loads(registry_path.read_text(encoding="utf-8"))

        manager.apply()
        second = json.loads(registry_path.read_text(encoding="utf-8"))

        # Strip volatile field before comparing structure.
        for data in (first, second):
            for group in data["feature_groups"].values():
                group.pop("applied_at", None)
        assert first == second

    def test_json_uses_sort_keys_and_indent_2(self, tmp_path: Path) -> None:
        """Registry JSON uses sorted keys and 2-space indentation."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        raw = cast(LocalProvider, manager._provider)._registry_path.read_text(encoding="utf-8")
        # Indented with 2 spaces: top-level keys start with two spaces.
        assert '\n  "' in raw
        # sort_keys=True: "feature_groups" (f) appears before "version" (v) at top level.
        assert raw.index('"feature_groups"') < raw.index('"version"')


class TestRegistryManagerApplyAllOrNothing:
    """Invalid definitions must leave the existing registry unchanged."""

    def test_invalid_definitions_raise_definition_error(self, tmp_path: Path) -> None:
        """Broken definition syntax raises DefinitionError."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "bad.py").write_text("def this is broken!!!")

        with pytest.raises(DefinitionError):
            manager.apply()

    def test_invalid_definitions_leave_registry_unchanged(self, tmp_path: Path) -> None:
        """A broken definition leaves the existing registry file unchanged."""
        manager = setup_manager(tmp_path)
        # First apply: register a valid group.
        (manager._definitions_path / "good.py").write_text(MINIMAL_DEF.format(varname="good", name="good_group"))
        manager.apply()

        registry_path = cast(LocalProvider, manager._provider)._registry_path
        original_content = registry_path.read_text(encoding="utf-8")

        # Add a broken definition file alongside the valid one.
        (manager._definitions_path / "bad.py").write_text("def !!!invalid")

        with pytest.raises(DefinitionError):
            manager.apply()

        # Registry file must be byte-for-byte unchanged.
        assert registry_path.read_text(encoding="utf-8") == original_content

    def test_validation_errors_collected_before_raising(self, tmp_path: Path) -> None:
        """All definition errors appear in the single DefinitionError message."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "bad.py").write_text("import nonexistent_package_xyz_abc_123")

        with pytest.raises(DefinitionError, match=r"bad\.py"):
            manager.apply()


class TestRegistryManagerLookup:
    """Tests for get_group(), list_groups(), and group_exists()."""

    def test_get_group_returns_correct_feature_group(self, tmp_path: Path) -> None:
        """get_group returns a FeatureGroup with the correct name and fields."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="my_group"))
        manager.apply()

        group = manager.get_group("my_group")

        assert group.name == "my_group"
        assert group.entity_key.name == "id"
        assert group.event_timestamp.name == "ts"
        assert len(group.features) == 1
        assert group.features[0].name == "value"

    def test_get_group_unknown_name_raises(self, tmp_path: Path) -> None:
        """get_group with an unknown name raises FeatureGroupNotFoundError."""
        manager = setup_manager(tmp_path)

        with pytest.raises(FeatureGroupNotFoundError, match=r"ghost"):
            manager.get_group("ghost")

    def test_get_group_actionable_error_message(self, tmp_path: Path) -> None:
        """Error message suggests running kitefs apply."""
        manager = setup_manager(tmp_path)

        with pytest.raises(FeatureGroupNotFoundError, match=r"kitefs apply"):
            manager.get_group("missing")

    def test_list_groups_empty_registry(self, tmp_path: Path) -> None:
        """list_groups returns an empty list when the registry has no groups."""
        manager = setup_manager(tmp_path)

        assert manager.list_groups() == []

    def test_list_groups_returns_summaries(self, tmp_path: Path) -> None:
        """list_groups returns summary dicts with name, entity_key, storage_target, and feature_count."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="my_group"))
        manager.apply()

        summaries = manager.list_groups()

        assert len(summaries) == 1
        s = summaries[0]
        assert s["name"] == "my_group"
        assert s["entity_key"] == "id"
        assert s["storage_target"] == "OFFLINE"
        assert s["feature_count"] == 1

    def test_list_groups_multiple(self, tmp_path: Path) -> None:
        """list_groups returns summaries for all registered groups."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "a.py").write_text(MINIMAL_DEF.format(varname="a", name="alpha"))
        (manager._definitions_path / "b.py").write_text(MINIMAL_DEF.format(varname="b", name="beta"))
        manager.apply()

        names = {s["name"] for s in manager.list_groups()}
        assert names == {"alpha", "beta"}

    def test_group_exists_true(self, tmp_path: Path) -> None:
        """group_exists returns True for a registered group."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="my_group"))
        manager.apply()

        assert manager.group_exists("my_group") is True

    def test_group_exists_false(self, tmp_path: Path) -> None:
        """group_exists returns False for a non-existent group."""
        manager = setup_manager(tmp_path)

        assert manager.group_exists("nonexistent") is False

    def test_get_group_round_trips_expect_constraints(self, tmp_path: Path) -> None:
        """Expect constraints survive serialize → persist → deserialize."""
        content = """\
from kitefs import (
    EntityKey, EventTimestamp, Expect, Feature, FeatureGroup,
    FeatureType, StorageTarget,
)
g = FeatureGroup(
    name="constrained",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[
        Feature(name="score", dtype=FeatureType.FLOAT,
                expect=Expect().not_null().gte(0.0).lte(1.0)),
        Feature(name="category", dtype=FeatureType.STRING,
                expect=Expect().one_of(["a", "b", "c"])),
    ],
)
"""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(content)
        manager.apply()

        group = manager.get_group("constrained")

        score = next(f for f in group.features if f.name == "score")
        category = next(f for f in group.features if f.name == "category")
        assert score.expect is not None
        assert score.expect._constraints == (
            {"type": "not_null"},
            {"type": "gte", "value": 0.0},
            {"type": "lte", "value": 1.0},
        )
        assert category.expect is not None
        assert category.expect._constraints == ({"type": "one_of", "values": ("a", "b", "c")},)

    def test_get_group_none_expect_round_trips(self, tmp_path: Path) -> None:
        """A feature with no expectations deserializes back to expect=None."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        group = manager.get_group("g")
        assert group.features[0].expect is None


class TestRegistryManagerStubs:
    """Stub methods raise NotImplementedError with informative messages."""

    def test_update_materialized_at_not_implemented(self, tmp_path: Path) -> None:
        """update_materialized_at raises NotImplementedError."""
        manager = setup_manager(tmp_path)
        with pytest.raises(NotImplementedError, match=r"Task 18"):
            manager.update_materialized_at("any_group", datetime.now(UTC))

    def test_validate_query_params_not_implemented(self, tmp_path: Path) -> None:
        """validate_query_params raises NotImplementedError."""
        manager = setup_manager(tmp_path)
        with pytest.raises(NotImplementedError, match=r"Task"):
            manager.validate_query_params("g", "*", None, None, "get_historical_features")


def _make_provider_error_with_cause(message: str, cause: Exception) -> ProviderError:
    """Create a ProviderError with an explicit __cause__ for testing."""
    exc = ProviderError(message)
    exc.__cause__ = cause
    return exc


class TestRegistryManagerLoadRegistry:
    """Tests for RegistryManager._load_registry() error handling."""

    def test_absent_registry_returns_empty_registry(self, tmp_path: Path) -> None:
        """No registry.json on disk — manager starts with an empty registry dict."""
        manager = setup_manager(tmp_path, seed_registry=False)

        assert manager._registry == {"version": "1.0", "feature_groups": {}}

    def test_absent_registry_apply_creates_file(self, tmp_path: Path) -> None:
        """apply() succeeds and creates registry.json when no file existed before."""
        manager = setup_manager(tmp_path, seed_registry=False)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))

        result = manager.apply()

        assert result.group_count == 1
        registry_path = cast(LocalProvider, manager._provider)._registry_path
        assert registry_path.exists()
        assert json.loads(registry_path.read_text(encoding="utf-8"))["version"] == "1.0"

    def test_malformed_registry_raises_registry_error(self, tmp_path: Path) -> None:
        """A corrupt registry.json raises RegistryError on construction."""
        config = make_local_config(tmp_path)
        config.storage_root.mkdir(parents=True, exist_ok=True)
        config.definitions_path.mkdir(parents=True, exist_ok=True)
        (config.storage_root / "registry.json").write_text("{invalid json!!!", encoding="utf-8")

        with pytest.raises(RegistryError, match=r"invalid JSON"):
            RegistryManager(LocalProvider(config), config.definitions_path)

    def test_io_error_during_load_raises_registry_error(self, tmp_path: Path) -> None:
        """A genuine I/O failure from the provider raises RegistryError, not silent fallback."""
        config = make_local_config(tmp_path)
        config.storage_root.mkdir(parents=True, exist_ok=True)
        config.definitions_path.mkdir(parents=True, exist_ok=True)

        provider = MagicMock()
        io_cause = OSError("Permission denied")
        provider.read_registry.side_effect = ProviderError("Failed to read registry: Permission denied.").__class__(
            "Failed to read registry: Permission denied."
        )
        # Attach the cause so _load_registry can distinguish it from "not found".
        provider.read_registry.side_effect = _make_provider_error_with_cause(
            "Failed to read registry: Permission denied.", io_cause
        )

        with pytest.raises(RegistryError, match=r"could not be read"):
            RegistryManager(provider, config.definitions_path)


class TestRegistryManagerApplyTimestamps:
    """Tests for applied_at timezone correctness and last_materialized_at edge cases."""

    def test_applied_at_is_utc_timezone_aware(self, tmp_path: Path) -> None:
        """applied_at must be a timezone-aware ISO 8601 string (UTC)."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(MINIMAL_DEF.format(varname="g", name="g"))
        manager.apply()

        applied_at = manager._registry["feature_groups"]["g"]["applied_at"]
        parsed = datetime.fromisoformat(applied_at)
        assert parsed.tzinfo is not None

    def test_new_group_gets_null_materialized_at_alongside_existing(self, tmp_path: Path) -> None:
        """When a new group is added via re-apply, it gets null last_materialized_at
        while the existing group's last_materialized_at is preserved."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "existing.py").write_text(MINIMAL_DEF.format(varname="existing", name="existing"))
        manager.apply()

        # Simulate materialization of the existing group.
        registry_path = cast(LocalProvider, manager._provider)._registry_path
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data["feature_groups"]["existing"]["last_materialized_at"] = "2025-06-01T12:00:00+00:00"
        registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Create a fresh manager (to pick up the file change) and add a second group.
        config2 = make_local_config(tmp_path)
        provider2 = LocalProvider(config2)
        manager2 = RegistryManager(provider2, manager._definitions_path)
        (manager2._definitions_path / "newgroup.py").write_text(MINIMAL_DEF.format(varname="newgroup", name="newgroup"))
        manager2.apply()

        fg = manager2._registry["feature_groups"]
        assert fg["existing"]["last_materialized_at"] == "2025-06-01T12:00:00+00:00"
        assert fg["newgroup"]["last_materialized_at"] is None


class TestRegistryManagerGetGroupDeserialization:
    """Tests that get_group() returns correctly typed enum values, not raw strings."""

    def test_get_group_deserializes_storage_target_and_validation_modes(self, tmp_path: Path) -> None:
        """Enum fields are deserialized to proper enum members, not strings."""
        content = """\
from kitefs import (
    EntityKey, EventTimestamp, Feature, FeatureGroup,
    FeatureType, StorageTarget, ValidationMode,
)
g = FeatureGroup(
    name="typed_group",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts", dtype=FeatureType.DATETIME),
    features=[Feature(name="v", dtype=FeatureType.FLOAT)],
    ingestion_validation=ValidationMode.FILTER,
    offline_retrieval_validation=ValidationMode.ERROR,
)
"""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "g.py").write_text(content)
        manager.apply()

        group = manager.get_group("typed_group")

        assert group.storage_target is StorageTarget.OFFLINE_AND_ONLINE
        assert group.ingestion_validation is ValidationMode.FILTER
        assert group.offline_retrieval_validation is ValidationMode.ERROR


class TestRegistryManagerReferenceUseCase:
    """Full reference use case produces a correct registry."""

    def test_reference_use_case_apply_succeeds(self, tmp_path: Path) -> None:
        """Reference use case definitions apply successfully."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "listing_features.py").write_text(LISTING_DEF)
        (manager._definitions_path / "town_market_features.py").write_text(TOWN_DEF)

        result = manager.apply()

        assert result.group_count == 2
        assert set(result.registered_groups) == {"listing_features", "town_market_features"}

    def test_reference_use_case_registry_structure(self, tmp_path: Path) -> None:
        """Registry JSON has correct structure for both reference use case groups."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "listing_features.py").write_text(LISTING_DEF)
        (manager._definitions_path / "town_market_features.py").write_text(TOWN_DEF)
        manager.apply()

        registry = manager._registry
        assert registry["version"] == "1.0"

        listing = registry["feature_groups"]["listing_features"]
        assert listing["storage_target"] == "OFFLINE"
        assert listing["entity_key"]["name"] == "listing_id"
        assert listing["entity_key"]["dtype"] == "INTEGER"
        assert listing["event_timestamp"]["dtype"] == "DATETIME"
        assert listing["ingestion_validation"] == "ERROR"
        assert listing["last_materialized_at"] is None
        assert len(listing["features"]) == 5
        assert listing["join_keys"] == [{"field_name": "town_id", "referenced_group": "town_market_features"}]

        town = registry["feature_groups"]["town_market_features"]
        assert town["storage_target"] == "OFFLINE_AND_ONLINE"
        assert town["entity_key"]["name"] == "town_id"

    def test_reference_use_case_get_group_round_trip(self, tmp_path: Path) -> None:
        """get_group round-trips all reference use case fields correctly."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "listing_features.py").write_text(LISTING_DEF)
        (manager._definitions_path / "town_market_features.py").write_text(TOWN_DEF)
        manager.apply()

        listing = manager.get_group("listing_features")
        town = manager.get_group("town_market_features")

        assert listing.name == "listing_features"
        assert listing.entity_key.name == "listing_id"
        assert len(listing.features) == 5
        assert len(listing.join_keys) == 1
        assert listing.join_keys[0].referenced_group == "town_market_features"
        assert listing.metadata.owner == "data-science-team"

        assert town.name == "town_market_features"
        assert town.storage_target.value == "OFFLINE_AND_ONLINE"
        assert town.features[0].expect is not None

    def test_reference_use_case_list_groups(self, tmp_path: Path) -> None:
        """list_groups includes correct summaries for both reference use case groups."""
        manager = setup_manager(tmp_path)
        (manager._definitions_path / "listing_features.py").write_text(LISTING_DEF)
        (manager._definitions_path / "town_market_features.py").write_text(TOWN_DEF)
        manager.apply()

        summaries = manager.list_groups()
        by_name = {s["name"]: s for s in summaries}

        assert by_name["listing_features"]["feature_count"] == 5
        assert by_name["listing_features"]["owner"] == "data-science-team"
        assert by_name["town_market_features"]["storage_target"] == "OFFLINE_AND_ONLINE"
        assert by_name["town_market_features"]["entity_key"] == "town_id"
