"""Tests for the configuration manager."""

from pathlib import Path

import pytest

from kitefs.config import AWSConfig, load_config
from kitefs.exceptions import ConfigurationError


def _write_yaml(tmp_path: Path, content: str) -> None:
    """Write a kitefs.yaml file in tmp_path."""
    (tmp_path / "kitefs.yaml").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


class TestLoadConfigValidLocal:
    """Valid local configuration loads correctly."""

    def test_all_attributes(self, tmp_path: Path) -> None:
        """Local config loads all attributes correctly."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        config = load_config(tmp_path)

        assert config.provider == "local"
        assert config.project_root == tmp_path.resolve()
        assert config.storage_root == (tmp_path / "feature_store").resolve()
        assert config.definitions_path == (tmp_path / "feature_store" / "definitions").resolve()
        assert config.aws is None

    def test_config_is_frozen(self, tmp_path: Path) -> None:
        """Config dataclass is frozen and cannot be mutated."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        config = load_config(tmp_path)

        with pytest.raises(AttributeError):
            config.provider = "aws"  # type: ignore[misc]


class TestLoadConfigValidAWS:
    """Valid AWS configuration loads correctly."""

    def test_all_attributes(self, tmp_path: Path) -> None:
        """AWS config loads all attributes including nested AWSConfig."""
        _write_yaml(
            tmp_path,
            (
                "provider: aws\n"
                "storage_root: ./feature_store/\n"
                "aws:\n"
                "  s3_bucket: my-bucket\n"
                "  s3_prefix: features/\n"
                "  dynamodb_table_prefix: kitefs_\n"
            ),
        )
        config = load_config(tmp_path)

        assert config.provider == "aws"
        assert isinstance(config.aws, AWSConfig)
        assert config.aws.s3_bucket == "my-bucket"
        assert config.aws.s3_prefix == "features/"
        assert config.aws.dynamodb_table_prefix == "kitefs_"


class TestLoadConfigStorageRootResolution:
    """storage_root is resolved to an absolute path relative to project_root."""

    def test_relative_path_resolved(self, tmp_path: Path) -> None:
        """storage_root is resolved to an absolute path relative to project_root."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./custom_store/\n")
        config = load_config(tmp_path)

        assert config.storage_root.is_absolute()
        assert config.storage_root == (tmp_path / "custom_store").resolve()

    def test_definitions_path_derived(self, tmp_path: Path) -> None:
        """definitions_path is derived as storage_root/definitions."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./my_store/\n")
        config = load_config(tmp_path)

        assert config.definitions_path == (tmp_path / "my_store" / "definitions").resolve()


class TestLoadConfigEnvVarOverrides:
    """Environment variables override kitefs.yaml values."""

    def test_override_provider(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """KITEFS_PROVIDER env var overrides the provider in kitefs.yaml."""
        _write_yaml(
            tmp_path,
            (
                "provider: local\n"
                "storage_root: ./feature_store/\n"
                "aws:\n"
                "  s3_bucket: my-bucket\n"
                "  s3_prefix: features/\n"
                "  dynamodb_table_prefix: kitefs_\n"
            ),
        )
        monkeypatch.setenv("KITEFS_PROVIDER", "aws")
        config = load_config(tmp_path)

        assert config.provider == "aws"
        assert config.aws is not None

    def test_override_storage_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """KITEFS_STORAGE_ROOT env var overrides the storage_root."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        monkeypatch.setenv("KITEFS_STORAGE_ROOT", "./overridden_store/")
        config = load_config(tmp_path)

        assert config.storage_root == (tmp_path / "overridden_store").resolve()

    def test_override_aws_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """AWS-specific env vars override the corresponding aws section fields."""
        _write_yaml(
            tmp_path,
            (
                "provider: aws\n"
                "storage_root: ./feature_store/\n"
                "aws:\n"
                "  s3_bucket: original-bucket\n"
                "  s3_prefix: original/\n"
                "  dynamodb_table_prefix: original_\n"
            ),
        )
        monkeypatch.setenv("KITEFS_AWS_S3_BUCKET", "new-bucket")
        monkeypatch.setenv("KITEFS_AWS_S3_PREFIX", "new/")
        monkeypatch.setenv("KITEFS_AWS_DYNAMODB_TABLE_PREFIX", "new_")
        config = load_config(tmp_path)

        assert config.aws is not None
        assert config.aws.s3_bucket == "new-bucket"
        assert config.aws.s3_prefix == "new/"
        assert config.aws.dynamodb_table_prefix == "new_"

    def test_env_var_creates_aws_section_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """AWS env vars create the aws section when absent in kitefs.yaml."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        monkeypatch.setenv("KITEFS_PROVIDER", "aws")
        monkeypatch.setenv("KITEFS_AWS_S3_BUCKET", "bucket")
        monkeypatch.setenv("KITEFS_AWS_S3_PREFIX", "prefix/")
        monkeypatch.setenv("KITEFS_AWS_DYNAMODB_TABLE_PREFIX", "pfx_")
        config = load_config(tmp_path)

        assert config.provider == "aws"
        assert config.aws is not None
        assert config.aws.s3_bucket == "bucket"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


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
    """AWS fields set to empty strings are treated as missing (not aws fixture.get() truthy)."""

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


class TestLoadConfigEnvVarStorageRootType:
    """An env-var-provided storage_root is always a str, passing the type check cleanly."""

    def test_env_var_storage_root_passes_type_check(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An env-var-provided storage_root passes the string type check."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        monkeypatch.setenv("KITEFS_STORAGE_ROOT", "./env_store/")
        config = load_config(tmp_path)
        assert config.storage_root == (tmp_path / "env_store").resolve()
