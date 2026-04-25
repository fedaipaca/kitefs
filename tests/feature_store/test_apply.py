"""Tests for FeatureStore.apply() — success and error paths."""

import json
from pathlib import Path

import pytest

from kitefs.exceptions import DefinitionError
from kitefs.feature_store import FeatureStore
from kitefs.registry import ApplyResult
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, setup_project

# A concrete definition for tests that only need one simple group.
_SIMPLE_DEF = MINIMAL_DEF.format(varname="listing_features", name="listing_features")


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
