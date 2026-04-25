"""Tests for FeatureStore constructor — explicit root, cwd discovery, and error paths."""

from pathlib import Path

import pytest

from kitefs.exceptions import ConfigurationError
from kitefs.feature_store import FeatureStore
from tests.helpers import MINIMAL_DEF, setup_project

# A concrete definition for tests that only need one simple group.
_SIMPLE_DEF = MINIMAL_DEF.format(varname="listing_features", name="listing_features")


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
