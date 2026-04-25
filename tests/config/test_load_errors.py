"""Tests for configuration loading error paths — missing files, malformed YAML, invalid fields."""

from pathlib import Path

import pytest

from kitefs.config import load_config
from kitefs.exceptions import ConfigurationError


def _write_yaml(tmp_path: Path, content: str) -> None:
    """Write a kitefs.yaml file in tmp_path."""
    (tmp_path / "kitefs.yaml").write_text(content, encoding="utf-8")


class TestLoadConfigFileNotFound:
    """Missing kitefs.yaml raises ConfigurationError mentioning kitefs init."""

    def test_error_message(self, tmp_path: Path) -> None:
        """Missing config error says no configuration file found."""
        with pytest.raises(ConfigurationError, match="No configuration file found"):
            load_config(tmp_path)

    def test_error_mentions_init(self, tmp_path: Path) -> None:
        """Missing config error suggests running kitefs init."""
        with pytest.raises(ConfigurationError, match="kitefs init"):
            load_config(tmp_path)


class TestLoadConfigMalformedYAML:
    """Malformed YAML raises ConfigurationError with parse context."""

    def test_error_message(self, tmp_path: Path) -> None:
        """Malformed YAML triggers a clear ConfigurationError."""
        _write_yaml(tmp_path, "provider: local\n  bad_indent: true\n")
        with pytest.raises(ConfigurationError, match="Malformed YAML"):
            load_config(tmp_path)


class TestLoadConfigMissingProvider:
    """Missing provider field raises ConfigurationError."""

    def test_error_message(self, tmp_path: Path) -> None:
        """Missing provider field produces an error mentioning provider."""
        _write_yaml(tmp_path, "storage_root: ./feature_store/\n")
        with pytest.raises(ConfigurationError, match="provider"):
            load_config(tmp_path)


class TestLoadConfigMissingStorageRoot:
    """Missing storage_root field raises ConfigurationError."""

    def test_error_message(self, tmp_path: Path) -> None:
        """Missing storage_root field produces an error mentioning storage_root."""
        _write_yaml(tmp_path, "provider: local\n")
        with pytest.raises(ConfigurationError, match="storage_root"):
            load_config(tmp_path)


class TestLoadConfigInvalidProvider:
    """Unsupported provider value raises ConfigurationError listing supported values."""

    def test_error_message(self, tmp_path: Path) -> None:
        """Unsupported provider value produces a clear error."""
        _write_yaml(tmp_path, "provider: gcp\nstorage_root: ./feature_store/\n")
        with pytest.raises(ConfigurationError, match=r"Unsupported provider.*gcp"):
            load_config(tmp_path)

    def test_lists_supported(self, tmp_path: Path) -> None:
        """Error lists the supported providers."""
        _write_yaml(tmp_path, "provider: gcp\nstorage_root: ./feature_store/\n")
        with pytest.raises(ConfigurationError, match=r"local.*aws"):
            load_config(tmp_path)


class TestLoadConfigAWSMissingFields:
    """Missing AWS fields when provider is aws raises ConfigurationError listing all missing."""

    def test_all_missing(self, tmp_path: Path) -> None:
        """All three missing AWS fields are reported in one error."""
        _write_yaml(tmp_path, "provider: aws\nstorage_root: ./feature_store/\n")
        with pytest.raises(ConfigurationError, match=r"aws\.s3_bucket.*aws\.s3_prefix.*aws\.dynamodb_table_prefix"):
            load_config(tmp_path)

    def test_partial_missing(self, tmp_path: Path) -> None:
        """Only the missing AWS fields appear in the error, not the present ones."""
        _write_yaml(
            tmp_path,
            ("provider: aws\nstorage_root: ./feature_store/\naws:\n  s3_bucket: my-bucket\n"),
        )
        with pytest.raises(ConfigurationError, match=r"aws\.s3_prefix.*aws\.dynamodb_table_prefix") as exc_info:
            load_config(tmp_path)
        # s3_bucket should NOT appear in error since it's provided
        assert "aws.s3_bucket" not in str(exc_info.value)


class TestLoadConfigEmptyFile:
    """Empty YAML file raises ConfigurationError."""

    def test_error_message(self, tmp_path: Path) -> None:
        """Empty file raises error expecting a YAML mapping."""
        _write_yaml(tmp_path, "")
        with pytest.raises(ConfigurationError, match="Expected a YAML mapping"):
            load_config(tmp_path)


class TestLoadConfigEnvVarInvalidProvider:
    """Environment variable with invalid provider raises ConfigurationError."""

    def test_error_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid provider via env var produces an error naming the provider."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        monkeypatch.setenv("KITEFS_PROVIDER", "gcp")
        with pytest.raises(ConfigurationError, match=r"Unsupported provider.*gcp"):
            load_config(tmp_path)

    def test_names_env_var_in_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Error message names the KITEFS_PROVIDER env var."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        monkeypatch.setenv("KITEFS_PROVIDER", "gcp")
        with pytest.raises(ConfigurationError, match="KITEFS_PROVIDER"):
            load_config(tmp_path)


class TestLoadConfigMultipleErrors:
    """Multiple validation errors are collected and reported together."""

    def test_collects_all_errors(self, tmp_path: Path) -> None:
        """Multiple missing fields are reported in a single error."""
        _write_yaml(tmp_path, "some_field: value\n")
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(tmp_path)
        message = str(exc_info.value)
        assert "provider" in message
        assert "storage_root" in message


class TestLoadConfigNonStringStorageRoot:
    """Non-string storage_root raises ConfigurationError instead of TypeError."""

    def test_raises_config_error(self, tmp_path: Path) -> None:
        """Non-string storage_root raises ConfigurationError."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: 123\n")
        with pytest.raises(ConfigurationError, match="storage_root"):
            load_config(tmp_path)

    def test_error_message_names_type(self, tmp_path: Path) -> None:
        """Error message names the actual type (int) of the invalid storage_root."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: 123\n")
        with pytest.raises(ConfigurationError, match="int"):
            load_config(tmp_path)


class TestLoadConfigEmptyStorageRoot:
    """Empty or whitespace-only storage_root raises ConfigurationError."""

    def test_empty_string(self, tmp_path: Path) -> None:
        """Empty string storage_root raises ConfigurationError."""
        _write_yaml(tmp_path, 'provider: local\nstorage_root: ""\n')
        with pytest.raises(ConfigurationError, match="storage_root"):
            load_config(tmp_path)

    def test_whitespace_only(self, tmp_path: Path) -> None:
        """Whitespace-only storage_root raises ConfigurationError."""
        _write_yaml(tmp_path, 'provider: local\nstorage_root: "   "\n')
        with pytest.raises(ConfigurationError, match="storage_root"):
            load_config(tmp_path)

    def test_error_mentions_how_to_fix(self, tmp_path: Path) -> None:
        """Error suggests feature_store as the expected value."""
        _write_yaml(tmp_path, 'provider: local\nstorage_root: ""\n')
        with pytest.raises(ConfigurationError, match="feature_store"):
            load_config(tmp_path)

    def test_empty_storage_root_from_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty KITEFS_STORAGE_ROOT env var raises ConfigurationError."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        monkeypatch.setenv("KITEFS_STORAGE_ROOT", "")
        with pytest.raises(ConfigurationError, match="KITEFS_STORAGE_ROOT"):
            load_config(tmp_path)


class TestLoadConfigNonMappingYAML:
    """YAML that parses to a non-mapping type raises ConfigurationError."""

    def test_yaml_list(self, tmp_path: Path) -> None:
        """YAML parsed as a list raises ConfigurationError."""
        _write_yaml(tmp_path, "- item1\n- item2\n")
        with pytest.raises(ConfigurationError, match="Expected a YAML mapping"):
            load_config(tmp_path)

    def test_yaml_scalar(self, tmp_path: Path) -> None:
        """YAML parsed as a scalar raises ConfigurationError."""
        _write_yaml(tmp_path, "just_a_string\n")
        with pytest.raises(ConfigurationError, match="Expected a YAML mapping"):
            load_config(tmp_path)


class TestLoadConfigAWSEmptyStringFields:
    """AWS fields set to empty strings are treated as missing."""

    def test_empty_s3_bucket_treated_as_missing(self, tmp_path: Path) -> None:
        """Empty string s3_bucket is treated as missing."""
        _write_yaml(
            tmp_path,
            (
                "provider: aws\nstorage_root: ./feature_store/\n"
                'aws:\n  s3_bucket: ""\n  s3_prefix: prefix/\n  dynamodb_table_prefix: pfx_\n'
            ),
        )
        with pytest.raises(ConfigurationError, match=r"aws\.s3_bucket"):
            load_config(tmp_path)
