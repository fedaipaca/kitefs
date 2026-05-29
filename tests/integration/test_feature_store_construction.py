"""Integration tests for FeatureStore construction and local provider wiring."""

from __future__ import annotations

import pytest

from kitefs.errors import ConfigurationError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.tmp_store import make_initialized_project


class TestLocalConstruction:
    """End-to-end FeatureStore() construction against a real local project."""

    def test_constructs_from_initialized_project(self, tmp_path, monkeypatch) -> None:
        """FeatureStore() succeeds after kitefs init."""
        make_initialized_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        fs = FeatureStore()
        assert fs.runtime_target == "local"

    def test_registry_read_returns_empty_registry(self, tmp_path, monkeypatch) -> None:
        """Local provider registry_store().read() returns empty feature_groups dict."""
        make_initialized_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        fs = FeatureStore()
        doc = fs._provider.registry_store().read()
        assert doc == {"feature_groups": {}}

    def test_registry_write_then_read_roundtrip(self, tmp_path, monkeypatch) -> None:
        """Writing to registry and reading back returns the same document."""
        make_initialized_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        fs = FeatureStore()
        store = fs._provider.registry_store()
        new_doc = {"feature_groups": {"mygroup": {"name": "mygroup"}}}
        store.write(new_doc)
        assert store.read() == new_doc

    def test_missing_yaml_raises_config_error(self, tmp_path, monkeypatch) -> None:
        """FeatureStore() raises ConfigurationError in an uninitialised directory."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigurationError) as exc_info:
            FeatureStore()
        msg = str(exc_info.value)
        assert "kitefs.yaml" in msg
        assert "kitefs init" in msg
