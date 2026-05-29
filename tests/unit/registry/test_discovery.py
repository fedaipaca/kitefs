"""Unit tests for registry discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from kitefs.errors import DefinitionDiscoveryError
from kitefs.registry.discovery import discover_feature_groups


def _make_simple_group_source(name: str) -> str:
    return f"""\
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, StorageTarget

{name} = FeatureGroup(
    name="{name}",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="ts"),
    features=[Feature(name="value", dtype=FeatureType.FLOAT)],
)
"""


class TestDiscoverFeatureGroups:
    """discover_feature_groups imports *.py files and collects FeatureGroup instances."""

    def test_returns_groups_from_two_files(self, tmp_path: Path) -> None:
        """Two files each declaring one FeatureGroup returns both groups."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "alpha.py").write_text(_make_simple_group_source("alpha"), encoding="utf-8")
        (defs / "beta.py").write_text(_make_simple_group_source("beta"), encoding="utf-8")

        groups = discover_feature_groups(defs)

        assert {g.name for g in groups} == {"alpha", "beta"}

    def test_returns_groups_sorted_by_file_order(self, tmp_path: Path) -> None:
        """Files are processed alphabetically so collection order is deterministic."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "z_group.py").write_text(_make_simple_group_source("z_group"), encoding="utf-8")
        (defs / "a_group.py").write_text(_make_simple_group_source("a_group"), encoding="utf-8")

        groups = discover_feature_groups(defs)

        assert [g.name for g in groups] == ["a_group", "z_group"]

    def test_multiple_groups_in_one_file(self, tmp_path: Path) -> None:
        """A single file may declare multiple FeatureGroup instances."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        src = _make_simple_group_source("group_one") + _make_simple_group_source("group_two")
        (defs / "two_groups.py").write_text(src, encoding="utf-8")

        groups = discover_feature_groups(defs)

        assert {g.name for g in groups} == {"group_one", "group_two"}

    def test_empty_directory_raises_discovery_error(self, tmp_path: Path) -> None:
        """Empty definitions directory raises DefinitionDiscoveryError."""
        defs = tmp_path / "definitions"
        defs.mkdir()

        with pytest.raises(DefinitionDiscoveryError) as exc_info:
            discover_feature_groups(defs)

        msg = str(exc_info.value)
        assert "FeatureGroup" in msg
        assert "declare" in msg

    def test_no_feature_groups_in_files_raises_discovery_error(self, tmp_path: Path) -> None:
        """A .py file with no FeatureGroup objects raises DefinitionDiscoveryError."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "empty.py").write_text("x = 42\n", encoding="utf-8")

        with pytest.raises(DefinitionDiscoveryError) as exc_info:
            discover_feature_groups(defs)

        assert "FeatureGroup" in str(exc_info.value)

    def test_import_error_raises_discovery_error_with_path(self, tmp_path: Path) -> None:
        """A file that raises on import produces DefinitionDiscoveryError mentioning the path."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "broken.py").write_text("raise ValueError('intentional error')\n", encoding="utf-8")

        with pytest.raises(DefinitionDiscoveryError) as exc_info:
            discover_feature_groups(defs)

        assert "broken.py" in str(exc_info.value)

    def test_syntax_error_raises_discovery_error_with_path(self, tmp_path: Path) -> None:
        """A file with a syntax error raises DefinitionDiscoveryError mentioning the path."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "syntax_error.py").write_text("def broken(:\n", encoding="utf-8")

        with pytest.raises(DefinitionDiscoveryError) as exc_info:
            discover_feature_groups(defs)

        assert "syntax_error.py" in str(exc_info.value)

    def test_does_not_recurse_into_subdirectories(self, tmp_path: Path) -> None:
        """Only top-level *.py files are discovered; subdirectories are ignored."""
        defs = tmp_path / "definitions"
        defs.mkdir()
        (defs / "top.py").write_text(_make_simple_group_source("top_group"), encoding="utf-8")
        sub = defs / "sub"
        sub.mkdir()
        (sub / "nested.py").write_text(_make_simple_group_source("nested_group"), encoding="utf-8")

        groups = discover_feature_groups(defs)

        assert [g.name for g in groups] == ["top_group"]
