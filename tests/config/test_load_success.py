"""Tests for successful configuration loading — local, AWS, resolution, and env var overrides."""

from pathlib import Path

import pytest

from kitefs.config import AWSConfig, load_config


def _write_yaml(tmp_path: Path, content: str) -> None:
    """Write a kitefs.yaml file in tmp_path."""
    (tmp_path / "kitefs.yaml").write_text(content, encoding="utf-8")


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


class TestLoadConfigEnvVarStorageRootType:
    """An env-var-provided storage_root is always a str, passing the type check cleanly."""

    def test_env_var_storage_root_passes_type_check(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An env-var-provided storage_root passes the string type check."""
        _write_yaml(tmp_path, "provider: local\nstorage_root: ./feature_store/\n")
        monkeypatch.setenv("KITEFS_STORAGE_ROOT", "./env_store/")
        config = load_config(tmp_path)
        assert config.storage_root == (tmp_path / "env_store").resolve()
