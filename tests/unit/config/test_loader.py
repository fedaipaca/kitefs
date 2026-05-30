"""Unit tests for kitefs.config.loader."""

from __future__ import annotations

import pytest

from kitefs.config.loader import RuntimeConfig, load_runtime_config
from kitefs.errors import ConfigurationError

_MINIMAL_YAML = """\
version: 1
project:
  name: testproject
runtime:
  target: local
"""

_PRODUCER_YAML = """\
version: 1
project:
  name: kitefs_featurestore_project
runtime:
  target: "${KITEFS_RUNTIME_TARGET:-local}"
remote:
  region: "${KITEFS_AWS_REGION:-eu-central-1}"
  registry:
    type: aws_s3
    bucket: "${KITEFS_REMOTE_REGISTRY_S3_BUCKET:-}"
    s3_prefix: "${KITEFS_REMOTE_REGISTRY_S3_PREFIX:-kitefs}"
  offline_store:
    type: aws_s3
    bucket: "${KITEFS_REMOTE_OFFLINE_S3_BUCKET:-}"
    s3_prefix: "${KITEFS_REMOTE_OFFLINE_S3_PREFIX:-kitefs}"
  online_store:
    type: aws_dynamodb
    dynamodb_table_prefix: "${KITEFS_REMOTE_ONLINE_DYNAMODB_TABLE_PREFIX:-kitefs_}"
"""


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "kitefs.yaml"
    p.write_text(content, encoding="utf-8")
    return tmp_path


class TestHappyPath:
    """Valid kitefs.yaml parses to a RuntimeConfig."""

    def test_returns_runtime_config(self, tmp_path) -> None:
        """Minimal valid YAML returns a RuntimeConfig with correct values."""
        root = _write_yaml(tmp_path, _MINIMAL_YAML)
        cfg = load_runtime_config(root)
        assert isinstance(cfg, RuntimeConfig)
        assert cfg.version == 1
        assert cfg.project_name == "testproject"
        assert cfg.target == "local"

    def test_producer_template_parses(self, tmp_path) -> None:
        """The producer scaffold template parses without error."""
        root = _write_yaml(tmp_path, _PRODUCER_YAML)
        cfg = load_runtime_config(root)
        assert cfg.target == "local"  # default from ${KITEFS_RUNTIME_TARGET:-local}

    def test_remote_section_preserved(self, tmp_path) -> None:
        """When remote section is present, RuntimeConfig.remote is a dict."""
        root = _write_yaml(tmp_path, _PRODUCER_YAML)
        cfg = load_runtime_config(root)
        assert isinstance(cfg.remote, dict)


class TestMissingFile:
    """Missing kitefs.yaml raises ConfigurationError."""

    def test_missing_yaml_raises_config_error(self, tmp_path) -> None:
        """Raises ConfigurationError when kitefs.yaml is absent."""
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(tmp_path)
        msg = str(exc_info.value)
        assert "kitefs.yaml" in msg
        assert "kitefs init" in msg

    def test_missing_yaml_does_not_search_parents(self, tmp_path) -> None:
        """Does not walk up to a parent directory looking for kitefs.yaml."""
        parent = tmp_path
        child = parent / "subdir"
        child.mkdir()
        (parent / "kitefs.yaml").write_text(_MINIMAL_YAML, encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_runtime_config(child)


class TestYamlParseError:
    """YAML syntax errors raise ConfigurationError naming the file."""

    def test_bad_yaml_raises_config_error(self, tmp_path) -> None:
        """Raises ConfigurationError on YAML parse error."""
        (tmp_path / "kitefs.yaml").write_text("key: [unclosed\n", encoding="utf-8")
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(tmp_path)
        msg = str(exc_info.value)
        assert "kitefs.yaml" in msg or "YAML" in msg

    def test_non_mapping_yaml_raises_config_error(self, tmp_path) -> None:
        """Raises ConfigurationError when YAML root is not a mapping."""
        (tmp_path / "kitefs.yaml").write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_runtime_config(tmp_path)


class TestInterpolation:
    """${VAR} and ${VAR:-default} expressions are resolved from env."""

    def test_var_substituted_from_env(self, tmp_path, monkeypatch) -> None:
        """${VAR} is replaced with the environment variable value."""
        monkeypatch.setenv("MY_PROJECT", "envproject")
        content = 'version: 1\nproject:\n  name: "${MY_PROJECT}"\nruntime:\n  target: local\n'
        root = _write_yaml(tmp_path, content)
        cfg = load_runtime_config(root)
        assert cfg.project_name == "envproject"

    def test_default_used_when_var_unset(self, tmp_path, monkeypatch) -> None:
        """${VAR:-default} uses the default when the env var is not set."""
        monkeypatch.delenv("MY_PROJECT", raising=False)
        content = 'version: 1\nproject:\n  name: "${MY_PROJECT:-fallback}"\nruntime:\n  target: local\n'
        root = _write_yaml(tmp_path, content)
        cfg = load_runtime_config(root)
        assert cfg.project_name == "fallback"

    def test_env_var_overrides_default(self, tmp_path, monkeypatch) -> None:
        """${VAR:-default} uses the env value when the var is set."""
        monkeypatch.setenv("MY_PROJECT", "fromenv")
        content = 'version: 1\nproject:\n  name: "${MY_PROJECT:-fallback}"\nruntime:\n  target: local\n'
        root = _write_yaml(tmp_path, content)
        cfg = load_runtime_config(root)
        assert cfg.project_name == "fromenv"

    def test_unset_var_without_default_resolves_to_empty_string(self, tmp_path, monkeypatch) -> None:
        """${VAR} resolves to empty string when the env var is not set."""
        monkeypatch.delenv("MY_BUCKET", raising=False)
        content = 'version: 1\nproject:\n  name: myproj\nruntime:\n  target: local\nremote:\n  region: "${MY_BUCKET}"\n'
        root = _write_yaml(tmp_path, content)
        cfg = load_runtime_config(root)
        assert cfg.remote == {"region": ""}

    def test_empty_env_var_with_default_uses_default(self, tmp_path, monkeypatch) -> None:
        """${VAR:-default} uses the default when the env var is set but empty."""
        monkeypatch.setenv("MY_PROJECT", "")
        content = 'version: 1\nproject:\n  name: "${MY_PROJECT:-fallback}"\nruntime:\n  target: local\n'
        root = _write_yaml(tmp_path, content)
        cfg = load_runtime_config(root)
        assert cfg.project_name == "fallback"

    def test_runtime_target_interpolated(self, tmp_path, monkeypatch) -> None:
        """${KITEFS_RUNTIME_TARGET:-local} resolves from env."""
        monkeypatch.setenv("KITEFS_RUNTIME_TARGET", "remote")
        content = _PRODUCER_YAML
        root = _write_yaml(tmp_path, content)
        cfg = load_runtime_config(root)
        assert cfg.target == "remote"


class TestRuntimeTargetOverride:
    """KITEFS_RUNTIME_TARGET env var overrides the resolved runtime.target."""

    def test_override_beats_hardcoded_local(self, tmp_path, monkeypatch) -> None:
        """Env override changes hardcoded 'local' target to 'remote'."""
        monkeypatch.setenv("KITEFS_RUNTIME_TARGET", "remote")
        root = _write_yaml(tmp_path, _PRODUCER_YAML)
        cfg = load_runtime_config(root)
        assert cfg.target == "remote"

    def test_no_override_when_var_absent(self, tmp_path, monkeypatch) -> None:
        """Without the env var, runtime.target from file is used."""
        monkeypatch.delenv("KITEFS_RUNTIME_TARGET", raising=False)
        root = _write_yaml(tmp_path, _MINIMAL_YAML)
        cfg = load_runtime_config(root)
        assert cfg.target == "local"


class TestFixedLiteralValidation:
    """remote.*.type fields must be bare literals, not interpolation expressions."""

    def test_rejects_interpolation_in_registry_type(self, tmp_path) -> None:
        """Raises ConfigurationError when remote.registry.type is an interpolation expr."""
        content = """\
version: 1
project:
  name: test
runtime:
  target: local
remote:
  registry:
    type: "${MY_REGISTRY_TYPE}"
  online_store:
    type: aws_dynamodb
"""
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        assert "remote.registry.type" in str(exc_info.value)

    def test_rejects_bad_literal_registry_type(self, tmp_path) -> None:
        """Raises ConfigurationError when remote.registry.type is an unsupported literal."""
        content = """\
version: 1
project:
  name: test
runtime:
  target: local
remote:
  registry:
    type: gcs_bucket
  online_store:
    type: aws_dynamodb
"""
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        assert "remote.registry.type" in str(exc_info.value)

    def test_rejects_interpolation_in_online_store_type(self, tmp_path) -> None:
        """Raises ConfigurationError when remote.online_store.type is interpolated."""
        content = """\
version: 1
project:
  name: test
runtime:
  target: local
remote:
  registry:
    type: aws_s3
  online_store:
    type: "${ONLINE_TYPE:-aws_dynamodb}"
"""
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        assert "remote.online_store.type" in str(exc_info.value)

    def test_valid_literals_pass(self, tmp_path) -> None:
        """Valid bare literals do not raise."""
        root = _write_yaml(tmp_path, _PRODUCER_YAML)
        cfg = load_runtime_config(root)
        assert cfg.target == "local"


class TestRequiredFieldValidation:
    """Missing required fields raise ConfigurationError naming the field."""

    def test_missing_version_raises(self, tmp_path) -> None:
        """Raises ConfigurationError when version is absent."""
        content = "project:\n  name: test\nruntime:\n  target: local\n"
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        assert "version" in str(exc_info.value)

    def test_missing_project_name_raises(self, tmp_path) -> None:
        """Raises ConfigurationError when project.name is absent."""
        content = "version: 1\nproject: {}\nruntime:\n  target: local\n"
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        assert "project.name" in str(exc_info.value)

    def test_missing_runtime_target_raises(self, tmp_path) -> None:
        """Raises ConfigurationError when runtime.target is absent."""
        content = "version: 1\nproject:\n  name: test\nruntime: {}\n"
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        assert "runtime.target" in str(exc_info.value)

    def test_remote_target_without_remote_section_raises(self, tmp_path) -> None:
        """Raises ConfigurationError when target is 'remote' but remote section is absent."""
        content = "version: 1\nproject:\n  name: test\nruntime:\n  target: remote\n"
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        assert "remote" in str(exc_info.value)

    def test_init_config_style_without_offline_store_is_valid(self, tmp_path) -> None:
        """Consumer-only config (registry + online_store, no offline_store) is valid."""
        content = """\
version: 1
project:
  name: consumer
runtime:
  target: remote
remote:
  region: us-east-1
  registry:
    type: aws_s3
    bucket: my-bucket
    s3_prefix: kitefs
  online_store:
    type: aws_dynamodb
    dynamodb_table_prefix: kitefs_
"""
        root = _write_yaml(tmp_path, content)
        cfg = load_runtime_config(root)
        assert cfg.target == "remote"
        assert isinstance(cfg.remote, dict)


class TestUnsupportedRuntimeTarget:
    """Unsupported runtime.target values raise ConfigurationError."""

    @pytest.mark.parametrize(
        "target",
        ["staging", "prod", "dev", "cloud", ""],
        ids=["staging", "prod", "dev", "cloud", "empty"],
    )
    def test_rejects_unsupported_target(self, tmp_path, target: str) -> None:
        """Raises ConfigurationError for any value other than local or remote."""
        content = f'version: 1\nproject:\n  name: test\nruntime:\n  target: "{target}"\n'
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        msg = str(exc_info.value)
        assert "local" in msg
        assert "remote" in msg

    def test_error_names_invalid_value(self, tmp_path) -> None:
        """ConfigurationError message includes the invalid target value."""
        content = "version: 1\nproject:\n  name: test\nruntime:\n  target: staging\n"
        root = _write_yaml(tmp_path, content)
        with pytest.raises(ConfigurationError) as exc_info:
            load_runtime_config(root)
        assert "staging" in str(exc_info.value)
