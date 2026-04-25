"""End-to-end tests for re-apply lifecycle — registry state across multiple apply cycles."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from kitefs.exceptions import DefinitionError, FeatureGroupNotFoundError
from kitefs.feature_store import FeatureStore
from tests.helpers import LISTING_DEF, MINIMAL_DEF, TOWN_DEF, setup_project


class TestReApplyLifecycle:
    """Registry state management across multiple apply cycles (full rebuild)."""

    def test_reapply_preserves_last_materialized_at(self, tmp_path: Path) -> None:
        """Existing group's last_materialized_at survives re-apply; new group gets null."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # Simulate materialization by patching registry.json directly
        registry_path = tmp_path / "feature_store" / "registry.json"
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data["feature_groups"]["listing_features"]["last_materialized_at"] = "2025-06-01T12:00:00+00:00"
        registry_path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")

        # Add a new group and re-apply
        defs_dir = tmp_path / "feature_store" / "definitions"
        new_group_def = MINIMAL_DEF.format(varname="extra_group", name="extra_group")
        (defs_dir / "extra.py").write_text(new_group_def, encoding="utf-8")
        fs2 = FeatureStore(project_root=tmp_path)
        fs2.apply()

        # Verify
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        assert data["feature_groups"]["listing_features"]["last_materialized_at"] == "2025-06-01T12:00:00+00:00"
        assert data["feature_groups"]["extra_group"]["last_materialized_at"] is None

        # Both applied_at should be recent
        for group_data in data["feature_groups"].values():
            applied = datetime.fromisoformat(group_data["applied_at"])
            assert applied is not None

    def test_reapply_removes_deleted_definitions(self, tmp_path: Path) -> None:
        """Deleting a definition file removes the group from registry on re-apply."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # Verify both exist
        assert len(fs.list_feature_groups()) == 2

        # Delete listing definition (not town, since listing references town via join key)
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "listing.py").unlink()

        # Re-apply
        fs2 = FeatureStore(project_root=tmp_path)
        result = fs2.apply()

        assert result.group_count == 1
        assert "listing_features" not in result.registered_groups

        # list_feature_groups also reflects the deletion
        summaries = fs2.list_feature_groups()
        assert isinstance(summaries, list)
        assert len(summaries) == 1
        assert summaries[0]["name"] == "town_market_features"

        # describe the deleted group raises error
        with pytest.raises(FeatureGroupNotFoundError):
            fs2.describe_feature_group("listing_features")

    def test_reapply_updates_modified_definitions(self, tmp_path: Path) -> None:
        """Modifying a definition is reflected in describe after re-apply."""
        setup_project(tmp_path, {"town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # Verify original has 1 feature
        desc = fs.describe_feature_group("town_market_features")
        assert isinstance(desc, dict)
        assert len(desc["features"]) == 1

        # Modify: add a second feature
        modified_town = TOWN_DEF.replace(
            "                expect=Expect().not_null().gt(0)),\n    ],",
            "                expect=Expect().not_null().gt(0)),\n"
            '        Feature(name="median_price", dtype=FeatureType.FLOAT,\n'
            '                description="Median sold price in this town"),\n    ],',
        )
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "town.py").write_text(modified_town, encoding="utf-8")

        # Re-apply with a fresh FeatureStore
        fs2 = FeatureStore(project_root=tmp_path)
        fs2.apply()

        desc2 = fs2.describe_feature_group("town_market_features")
        assert isinstance(desc2, dict)
        assert len(desc2["features"]) == 2
        feature_names = {f["name"] for f in desc2["features"]}
        assert "avg_price_per_sqm" in feature_names
        assert "median_price" in feature_names

    def test_reapply_all_or_nothing_on_validation_failure(self, tmp_path: Path) -> None:
        """Adding a broken definition fails apply without altering the existing registry."""
        setup_project(tmp_path, {"listing.py": LISTING_DEF, "town.py": TOWN_DEF})
        fs = FeatureStore(project_root=tmp_path)
        fs.apply()

        # Snapshot the registry before the bad apply
        registry_path = tmp_path / "feature_store" / "registry.json"
        original_content = registry_path.read_text(encoding="utf-8")

        # Add a broken definition
        defs_dir = tmp_path / "feature_store" / "definitions"
        (defs_dir / "broken.py").write_text("import nonexistent_module_xyz\n", encoding="utf-8")

        # Re-apply should fail
        fs2 = FeatureStore(project_root=tmp_path)
        with pytest.raises(DefinitionError):
            fs2.apply()

        # Registry must be unchanged
        assert registry_path.read_text(encoding="utf-8") == original_content

        # Original groups still accessible via a new FeatureStore
        fs3 = FeatureStore(project_root=tmp_path)
        summaries = fs3.list_feature_groups()
        assert isinstance(summaries, list)
        assert len(summaries) == 2
        names = {s["name"] for s in summaries}
        assert names == {"listing_features", "town_market_features"}
