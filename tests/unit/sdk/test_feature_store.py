"""Unit tests for FeatureStore construction."""

from __future__ import annotations

import pytest

from kitefs.errors import ConfigurationError
from kitefs.sdk.feature_store import FeatureStore
from tests.helpers.tmp_store import make_initialized_project

_MINIMAL_YAML = """\
version: 1
project:
  name: testproject
runtime:
  target: local
"""

_YAML_WITH_REMOTE = """\
version: 1
project:
  name: testproject
runtime:
  target: local
remote:
  region: us-east-1
  registry:
    type: aws_s3
    bucket: my-bucket
    s3_prefix: kitefs
  offline_store:
    type: aws_s3
    bucket: my-bucket
    s3_prefix: kitefs
  online_store:
    type: aws_dynamodb
    dynamodb_table_prefix: kitefs_
"""


class TestConstruction:
    """FeatureStore() constructs successfully in an initialized project."""

    def test_constructs_in_initialized_project(self, tmp_path, monkeypatch) -> None:
        """FeatureStore() does not raise in a valid initialized project."""
        make_initialized_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        fs = FeatureStore()
        assert fs is not None

    def test_runtime_target_is_local(self, tmp_path, monkeypatch) -> None:
        """runtime_target property returns 'local' for default config."""
        make_initialized_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        fs = FeatureStore()
        assert fs.runtime_target == "local"


class TestMissingConfig:
    """FeatureStore() raises ConfigurationError when kitefs.yaml is absent."""

    def test_raises_config_error(self, tmp_path, monkeypatch) -> None:
        """Raises ConfigurationError in a directory without kitefs.yaml."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigurationError) as exc_info:
            FeatureStore()
        assert "kitefs.yaml" in str(exc_info.value)
        assert "kitefs init" in str(exc_info.value)


class TestRuntimeOverride:
    """KITEFS_RUNTIME_TARGET env var overrides the config file target."""

    def test_override_to_remote(self, tmp_path, monkeypatch) -> None:
        """KITEFS_RUNTIME_TARGET=remote overrides hardcoded local target."""
        (tmp_path / "kitefs.yaml").write_text(_YAML_WITH_REMOTE, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("KITEFS_RUNTIME_TARGET", "remote")
        fs = FeatureStore()
        assert fs.runtime_target == "remote"
