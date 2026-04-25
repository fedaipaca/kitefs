"""Tests for the FeatureStore SDK entry point — constructor, apply(), list, and describe."""

import json
from pathlib import Path

import pytest

from kitefs.exceptions import ConfigurationError, DefinitionError, FeatureGroupNotFoundError
from kitefs.feature_store import FeatureStore
from kitefs.registry import ApplyResult
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, setup_project

# A concrete definition for tests that only need one simple group.
_SIMPLE_DEF = MINIMAL_DEF.format(varname="listing_features", name="listing_features")


# ---------------------------------------------------------------------------
# FeatureStore constructor — success paths
# ---------------------------------------------------------------------------


class TestConstructorExplicitRoot:
    """FeatureStore(project_root=...) with explicit Path or str."""

    def test_accepts_path(self, tmp_path: Path) -> None:
        """FeatureStore accepts an explicit Path to the project root."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})

        fs = FeatureStore(project_root=tmp_path)

        assert fs is not None

    def test_accepts_str(self, tmp_path: Path) -> None:
        """FeatureStore accepts a string path to the project root."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})

        fs = FeatureStore(project_root=str(tmp_path))

        assert fs is not None


class TestConstructorCwdDiscovery:
    """FeatureStore() with no project_root walks up from cwd."""

    def test_finds_project_in_ancestor(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FeatureStore discovers kitefs.yaml by walking up from a nested cwd."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        nested = tmp_path / "some" / "deep" / "subdir"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        fs = FeatureStore()

        result = fs.apply()
        assert result.group_count >= 1

    def test_finds_project_at_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FeatureStore discovers kitefs.yaml when cwd is the project root."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        monkeypatch.chdir(tmp_path)

        fs = FeatureStore()

        result = fs.apply()
        assert result.group_count >= 1


# ---------------------------------------------------------------------------
# FeatureStore constructor — error paths
# ---------------------------------------------------------------------------


class TestConstructorErrors:
    """Constructor raises ConfigurationError when no project is found."""

    def test_no_project_in_tree_raises_configuration_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ConfigurationError raised when no kitefs.yaml exists in the directory tree."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigurationError, match=r"No KiteFS project found"):
            FeatureStore()

    def test_error_message_suggests_kitefs_init(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Error message suggests running kitefs init to create a project."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigurationError, match=r"kitefs init"):
            FeatureStore()

    def test_explicit_path_without_config_raises_configuration_error(self, tmp_path: Path) -> None:
        """An explicit project_root that lacks kitefs.yaml fails immediately."""
        with pytest.raises(ConfigurationError, match=r"No KiteFS project found"):
            FeatureStore(project_root=tmp_path)

    def test_explicit_nonexistent_directory_raises_configuration_error(self, tmp_path: Path) -> None:
        """A path that does not exist at all raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match=r"No KiteFS project found"):
            FeatureStore(project_root=tmp_path / "does_not_exist")

    def test_explicit_nested_path_does_not_walk_parents(self, tmp_path: Path) -> None:
        """Passing a child directory does not trigger upward discovery."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        child = tmp_path / "some" / "subdir"
        child.mkdir(parents=True)

        with pytest.raises(ConfigurationError, match=r"No KiteFS project found"):
            FeatureStore(project_root=child)


# ---------------------------------------------------------------------------
# FeatureStore.apply() — success paths
# ---------------------------------------------------------------------------


class TestApplySuccess:
    """apply() delegates to RegistryManager and returns ApplyResult."""

    def test_returns_apply_result(self, tmp_path: Path) -> None:
        """apply() returns an ApplyResult dataclass."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        fs = FeatureStore(project_root=tmp_path)

        result = fs.apply()

        assert isinstance(result, ApplyResult)

    def test_group_count_matches_definitions(self, tmp_path: Path) -> None:
        """group_count reflects the number of discovered definitions."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        fs = FeatureStore(project_root=tmp_path)

        result = fs.apply()

        assert result.group_count == 1

    def test_registered_groups_contains_group_name(self, tmp_path: Path) -> None:
        """registered_groups tuple contains the name of the applied group."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        fs = FeatureStore(project_root=tmp_path)

        result = fs.apply()

        assert "listing_features" in result.registered_groups

    def test_multiple_definitions(self, tmp_path: Path) -> None:
        """Applying two definition files registers both groups."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)

        result = fs.apply()

        assert result.group_count == 2
        assert result.registered_groups == ("listing_features", "town_market_features")

    def test_registered_groups_are_sorted(self, tmp_path: Path) -> None:
        """Registered groups tuple is sorted alphabetically."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)

        result = fs.apply()

        assert result.registered_groups == tuple(sorted(result.registered_groups))

    def test_registry_json_updated(self, tmp_path: Path) -> None:
        """apply() writes the group to registry.json on disk."""
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        fs = FeatureStore(project_root=tmp_path)

        fs.apply()

        registry_path = tmp_path / "feature_store" / "registry.json"
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert "listing_features" in data["feature_groups"]
        assert data["version"] == "1.0"


# ---------------------------------------------------------------------------
# FeatureStore.apply() — error paths
# ---------------------------------------------------------------------------


class TestApplyErrors:
    """apply() propagates errors from the registry layer."""

    def test_invalid_definitions_raises_definition_error(self, tmp_path: Path) -> None:
        """A definition with an import error raises DefinitionError."""
        bad_def = "import nonexistent_module_xyz\n"
        setup_project(tmp_path, {"broken.py": bad_def})
        fs = FeatureStore(project_root=tmp_path)

        with pytest.raises(DefinitionError):
            fs.apply()

    def test_no_definitions_raises_definition_error(self, tmp_path: Path) -> None:
        """An empty definitions directory raises DefinitionError."""
        setup_project(tmp_path)
        fs = FeatureStore(project_root=tmp_path)

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            fs.apply()


# ---------------------------------------------------------------------------
# FeatureStore.list_feature_groups() — success paths
# ---------------------------------------------------------------------------


class TestListFeatureGroupsSuccess:
    """list_feature_groups() returns summaries from the registry."""

    def test_returns_list_of_summary_dicts(self, tmp_path: Path) -> None:
        """Default return is a list of summary dicts, one per group."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.list_feature_groups()

        assert isinstance(result, list)
        assert len(result) == 2
        names = {s["name"] for s in result}
        assert names == {"listing_features", "town_market_features"}

    def test_summary_contains_required_fields(self, tmp_path: Path) -> None:
        """Each summary dict includes name, owner, entity_key, storage_target, feature_count."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.list_feature_groups()

        for summary in result:
            assert "name" in summary
            assert "owner" in summary
            assert "entity_key" in summary
            assert "storage_target" in summary
            assert "feature_count" in summary

    def test_empty_registry_returns_empty_list(self, tmp_path: Path) -> None:
        """An empty registry returns an empty list, not an error."""
        setup_project(tmp_path)
        fs = FeatureStore(project_root=tmp_path)

        result = fs.list_feature_groups()

        assert result == []

    def test_json_format_returns_json_string(self, tmp_path: Path) -> None:
        """format='json' returns a JSON string instead of a list."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.list_feature_groups(format="json")

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_target_writes_json_file(self, tmp_path: Path) -> None:
        """target parameter writes summaries as JSON to the specified file."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()
        output_path = tmp_path / "output.json"

        result = fs.list_feature_groups(target=str(output_path))

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 2
        assert isinstance(result, str)

    def test_target_without_format_writes_json(self, tmp_path: Path) -> None:
        """target alone implies JSON serialization."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()
        output_path = tmp_path / "out.json"

        fs.list_feature_groups(target=str(output_path))

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# FeatureStore.describe_feature_group() — success paths
# ---------------------------------------------------------------------------


class TestDescribeFeatureGroupSuccess:
    """describe_feature_group() returns the full definition from the registry."""

    def test_returns_full_definition_dict(self, tmp_path: Path) -> None:
        """Default return is a dict with all registry fields for the group."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("listing_features")

        assert isinstance(result, dict)
        assert result["name"] == "listing_features"
        assert "entity_key" in result
        assert "event_timestamp" in result
        assert "features" in result
        assert "join_keys" in result
        assert "ingestion_validation" in result
        assert "offline_retrieval_validation" in result
        assert "metadata" in result
        assert "applied_at" in result
        assert "last_materialized_at" in result

    def test_metadata_fields_present(self, tmp_path: Path) -> None:
        """Metadata owner and description are included in the describe output."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("listing_features")

        assert isinstance(result, dict)
        meta = result["metadata"]
        assert meta["owner"] == "data-science-team"
        assert meta["description"] == "Historical sold listing attributes and prices"

    def test_last_materialized_at_present_even_when_none(self, tmp_path: Path) -> None:
        """last_materialized_at is included as null for groups not yet materialized."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("listing_features")

        assert isinstance(result, dict)
        assert "last_materialized_at" in result
        assert result["last_materialized_at"] is None

    def test_json_format_returns_json_string(self, tmp_path: Path) -> None:
        """format='json' returns a JSON string of the full group definition."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("listing_features", format="json")

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["name"] == "listing_features"

    def test_target_writes_json_file(self, tmp_path: Path) -> None:
        """target parameter writes the full definition as JSON to the specified file."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()
        output_path = tmp_path / "describe_out.json"

        result = fs.describe_feature_group("listing_features", target=str(output_path))

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["name"] == "listing_features"
        assert isinstance(result, str)

    def test_storage_target_value(self, tmp_path: Path) -> None:
        """storage_target is serialized as the enum value string."""
        setup_project(tmp_path, {"town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.describe_feature_group("town_market_features")

        assert isinstance(result, dict)
        assert result["storage_target"] == "OFFLINE_AND_ONLINE"


# ---------------------------------------------------------------------------
# FeatureStore.describe_feature_group() — error paths
# ---------------------------------------------------------------------------


class TestDescribeFeatureGroupErrors:
    """describe_feature_group() raises FeatureGroupNotFoundError for missing groups."""

    def test_unknown_name_raises_feature_group_not_found_error(self, tmp_path: Path) -> None:
        """Describing a non-existent group raises FeatureGroupNotFoundError."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        with pytest.raises(FeatureGroupNotFoundError, match=r"ghost"):
            fs.describe_feature_group("ghost")

    def test_error_message_suggests_kitefs_list(self, tmp_path: Path) -> None:
        """Error message suggests running kitefs list to see available groups."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        with pytest.raises(FeatureGroupNotFoundError, match=r"kitefs list"):
            fs.describe_feature_group("nonexistent")


# ---------------------------------------------------------------------------
# FeatureStore.list_feature_groups() — JSON summary fields completeness
# ---------------------------------------------------------------------------


class TestListFeatureGroupsJsonFields:
    """list_feature_groups(format='json') output contains all required summary fields."""

    def test_json_output_has_all_required_summary_fields(self, tmp_path: Path) -> None:
        """JSON list output includes name, owner, entity_key, storage_target, feature_count."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.list_feature_groups(format="json")

        assert isinstance(result, str)
        parsed = json.loads(result)
        for summary in parsed:
            assert set(summary.keys()) >= {"name", "owner", "entity_key", "storage_target", "feature_count"}

    def test_json_field_types_are_correct(self, tmp_path: Path) -> None:
        """JSON summary fields have the correct Python types after parsing."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        result = fs.list_feature_groups(format="json")

        assert isinstance(result, str)
        parsed = json.loads(result)
        summary = parsed[0]
        assert isinstance(summary["name"], str)
        assert isinstance(summary["entity_key"], str)
        assert isinstance(summary["storage_target"], str)
        assert isinstance(summary["feature_count"], int)
        # owner may be str or None
        assert summary["owner"] is None or isinstance(summary["owner"], str)


# ---------------------------------------------------------------------------
# FeatureStore.describe_feature_group() — returns independent copy
# ---------------------------------------------------------------------------


class TestDescribeFeatureGroupReturnsCopy:
    """describe_feature_group() returns a copy; mutating it does not affect the registry."""

    def test_mutating_result_does_not_affect_subsequent_call(self, tmp_path: Path) -> None:
        """Mutating a returned dict does not corrupt subsequent describe calls."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        first = fs.describe_feature_group("listing_features")
        assert isinstance(first, dict)
        original_entity_key_name = first["entity_key"]["name"]

        # Mutate a nested value in the returned dict.
        first["entity_key"]["name"] = "mutated_name"

        second = fs.describe_feature_group("listing_features")
        assert isinstance(second, dict)
        assert second["entity_key"]["name"] == original_entity_key_name
