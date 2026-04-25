"""Tests for FeatureStore.list_feature_groups() — success paths and JSON fields."""

import json
from pathlib import Path

from kitefs.feature_store import FeatureStore
from tests.helpers import LISTING_DEF, TOWN_DEF, setup_project


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
