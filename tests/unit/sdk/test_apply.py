"""Unit tests for FeatureStore.apply() orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kitefs.errors import DefinitionDiscoveryError, DefinitionValidationError
from kitefs.sdk.feature_store import FeatureStore
from kitefs.sdk.results import ApplyResult
from tests.helpers.tmp_store import make_initialized_project

_TOWN_MARKET_SRC = """\
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, StorageTarget

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(name="town_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="event_timestamp"),
    features=[Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT)],
)
"""

_LISTING_SRC = """\
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, JoinKey, StorageTarget

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[Feature(name="net_area", dtype=FeatureType.INTEGER)],
    join_keys=[JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="town_market_features")],
)
"""


def _setup_project(tmp_path: Path) -> Path:
    make_initialized_project(tmp_path)
    return tmp_path


class TestApplyHappyPath:
    """FeatureStore.apply() returns ApplyResult and writes registry.json."""

    def test_returns_apply_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply() returns ApplyResult with registered_groups sorted and published=False."""
        root = _setup_project(tmp_path)
        defs = root / "feature_store" / "definitions"
        (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
        defs_town = defs / "town_market_features.py"
        defs_town.write_text(_TOWN_MARKET_SRC, encoding="utf-8")
        monkeypatch.chdir(root)

        result = FeatureStore().apply()

        assert isinstance(result, ApplyResult)
        assert result.registered_groups == ["listing_features", "town_market_features"]
        assert result.published is False

    def test_writes_registry_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply() writes both groups into registry.json."""
        root = _setup_project(tmp_path)
        defs = root / "feature_store" / "definitions"
        (defs / "listing_features.py").write_text(_LISTING_SRC, encoding="utf-8")
        monkeypatch.chdir(root)

        FeatureStore().apply()

        doc = json.loads((root / "feature_store" / "registry.json").read_text())
        assert "listing_features" in doc["feature_groups"]

    def test_applied_at_is_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply() sets applied_at for each group in the registry."""
        root = _setup_project(tmp_path)
        monkeypatch.chdir(root)

        FeatureStore().apply()

        doc = json.loads((root / "feature_store" / "registry.json").read_text())
        entry = doc["feature_groups"]["town_market_features"]
        assert entry["applied_at"] is not None
        assert entry["applied_at"].endswith("Z")

    def test_last_materialized_at_starts_null(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply() sets last_materialized_at to null for a freshly applied group."""
        root = _setup_project(tmp_path)
        monkeypatch.chdir(root)

        FeatureStore().apply()

        doc = json.loads((root / "feature_store" / "registry.json").read_text())
        assert doc["feature_groups"]["town_market_features"]["last_materialized_at"] is None

    def test_preserves_last_materialized_at_on_reapply(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A second apply() preserves the existing last_materialized_at value."""
        root = _setup_project(tmp_path)
        monkeypatch.chdir(root)

        # Manually inject a last_materialized_at into the registry.
        prior_ts = "2026-05-01T00:00:00.000000Z"
        registry_path = root / "feature_store" / "registry.json"
        doc = json.loads(registry_path.read_text())
        doc["feature_groups"]["town_market_features"] = {"last_materialized_at": prior_ts}
        registry_path.write_text(json.dumps(doc), encoding="utf-8")

        FeatureStore().apply()

        updated = json.loads(registry_path.read_text())
        assert updated["feature_groups"]["town_market_features"]["last_materialized_at"] == prior_ts


class TestApplyErrors:
    """FeatureStore.apply() raises appropriate errors and leaves registry unchanged."""

    def test_no_groups_raises_discovery_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply() raises DefinitionDiscoveryError when definitions/ has no FeatureGroups."""
        root = _setup_project(tmp_path)
        (root / "feature_store" / "definitions" / "town_market_features.py").unlink()
        monkeypatch.chdir(root)

        with pytest.raises(DefinitionDiscoveryError):
            FeatureStore().apply()

    def test_registry_unchanged_on_discovery_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Registry file is not modified when DefinitionDiscoveryError is raised."""
        root = _setup_project(tmp_path)
        registry_path = root / "feature_store" / "registry.json"
        original_content = registry_path.read_text(encoding="utf-8")
        (root / "feature_store" / "definitions" / "town_market_features.py").unlink()
        monkeypatch.chdir(root)

        with pytest.raises(DefinitionDiscoveryError):
            FeatureStore().apply()

        assert registry_path.read_text(encoding="utf-8") == original_content

    def test_validation_error_leaves_registry_unchanged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply() leaves registry unchanged when cross-definition validation fails."""
        root = _setup_project(tmp_path)
        registry_path = root / "feature_store" / "registry.json"
        original_content = registry_path.read_text(encoding="utf-8")

        # Write listing_features.py referencing a group that doesn't exist.
        bad_src = """\
from kitefs import FeatureGroup, EntityKey, EventTimestamp, Feature, FeatureType, JoinKey, StorageTarget

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(name="listing_id", dtype=FeatureType.INTEGER),
    event_timestamp=EventTimestamp(name="sold_at"),
    features=[Feature(name="net_area", dtype=FeatureType.INTEGER)],
    join_keys=[JoinKey(name="town_id", dtype=FeatureType.INTEGER, referenced_group="missing_group")],
)
"""
        (root / "feature_store" / "definitions" / "listing_features.py").write_text(bad_src, encoding="utf-8")
        monkeypatch.chdir(root)

        with pytest.raises(DefinitionValidationError):
            FeatureStore().apply()

        assert registry_path.read_text(encoding="utf-8") == original_content


class TestApplyWithRemoteRuntimeTarget:
    """FeatureStore.apply() writes the local registry even when runtime.target is remote."""

    def test_writes_local_registry_when_remote_target(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply() writes feature_store/registry.json locally regardless of runtime.target."""
        root = _setup_project(tmp_path)
        monkeypatch.chdir(root)
        monkeypatch.setenv("KITEFS_RUNTIME_TARGET", "remote")

        result = FeatureStore().apply()

        assert isinstance(result, ApplyResult)
        assert result.published is False
        doc = json.loads((root / "feature_store" / "registry.json").read_text())
        assert "town_market_features" in doc["feature_groups"]


class TestApplyUsesConstructionRoot:
    """FeatureStore.apply() uses the root captured at construction, not the current cwd."""

    def test_uses_construction_root_after_cwd_change(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply() updates the registry at the construction root even after cwd changes."""
        root = _setup_project(tmp_path)
        monkeypatch.chdir(root)
        fs = FeatureStore()

        # Change cwd to an unrelated directory after construction.
        monkeypatch.chdir(tmp_path.parent)

        fs.apply()

        doc = json.loads((root / "feature_store" / "registry.json").read_text())
        assert "town_market_features" in doc["feature_groups"]
