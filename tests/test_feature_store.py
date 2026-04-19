"""Tests for the FeatureStore SDK entry point — constructor wiring and apply()."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kitefs.cli import cli
from kitefs.exceptions import ConfigurationError, DefinitionError
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
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})

        fs = FeatureStore(project_root=tmp_path)

        assert fs is not None

    def test_accepts_str(self, tmp_path: Path) -> None:
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})

        fs = FeatureStore(project_root=str(tmp_path))

        assert fs is not None


class TestConstructorCwdDiscovery:
    """FeatureStore() with no project_root walks up from cwd."""

    def test_finds_project_in_ancestor(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        nested = tmp_path / "some" / "deep" / "subdir"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        fs = FeatureStore()

        result = fs.apply()
        assert result.group_count >= 1

    def test_finds_project_at_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigurationError, match=r"No KiteFS project found"):
            FeatureStore()

    def test_error_message_suggests_kitefs_init(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        fs = FeatureStore(project_root=tmp_path)

        result = fs.apply()

        assert isinstance(result, ApplyResult)

    def test_group_count_matches_definitions(self, tmp_path: Path) -> None:
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        fs = FeatureStore(project_root=tmp_path)

        result = fs.apply()

        assert result.group_count == 1

    def test_registered_groups_contains_group_name(self, tmp_path: Path) -> None:
        setup_project(tmp_path, {"listing.py": _SIMPLE_DEF})
        fs = FeatureStore(project_root=tmp_path)

        result = fs.apply()

        assert "listing_features" in result.registered_groups

    def test_multiple_definitions(self, tmp_path: Path) -> None:
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
        bad_def = "import nonexistent_module_xyz\n"
        setup_project(tmp_path, {"broken.py": bad_def})
        fs = FeatureStore(project_root=tmp_path)

        with pytest.raises(DefinitionError):
            fs.apply()

    def test_no_definitions_raises_definition_error(self, tmp_path: Path) -> None:
        setup_project(tmp_path)
        fs = FeatureStore(project_root=tmp_path)

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            fs.apply()


# ---------------------------------------------------------------------------
# End-to-end — init → define → apply → verify
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Full workflow: CLI init → write definition → SDK apply → verify registry."""

    def test_init_then_apply_produces_valid_registry(self, tmp_path: Path) -> None:
        # 1. kitefs init
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        # 2. Write a real definition
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").write_text(_SIMPLE_DEF, encoding="utf-8")

        # 3. SDK apply
        fs = FeatureStore(project_root=tmp_path)
        apply_result = fs.apply()

        # 4. Verify
        assert apply_result.group_count == 1
        assert "listing_features" in apply_result.registered_groups

        registry_path = tmp_path / "feature_store" / "registry.json"
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert "listing_features" in data["feature_groups"]
        assert data["version"] == "1.0"

    def test_init_scaffold_with_no_real_definitions_raises_definition_error(self, tmp_path: Path) -> None:
        """An init scaffold with only example_features.py raises DefinitionError."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        fs = FeatureStore(project_root=tmp_path)

        with pytest.raises(DefinitionError, match=r"No feature group definitions found"):
            fs.apply()
