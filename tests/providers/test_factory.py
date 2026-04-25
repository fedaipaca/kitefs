"""Tests for the provider factory — correct dispatch and error cases."""

from pathlib import Path

import pytest
from helpers import make_local_config

from kitefs.config import AWSConfig, Config
from kitefs.exceptions import ProviderError
from kitefs.providers import LocalProvider, StorageProvider, create_provider


def _make_aws_config(tmp_path: Path) -> Config:
    """Build a minimal AWS Config for factory error tests."""
    storage_root = tmp_path / "feature_store"
    return Config(
        provider="aws",
        project_root=tmp_path,
        storage_root=storage_root,
        definitions_path=storage_root / "definitions",
        aws=AWSConfig(
            s3_bucket="my-bucket",
            s3_prefix="kitefs/",
            dynamodb_table_prefix="kitefs_",
        ),
    )


class TestCreateProvider:
    """Provider factory — correct dispatch and error cases."""

    def test_local_config_returns_local_provider(self, tmp_path: Path) -> None:
        """Factory returns a LocalProvider for local config."""
        config = make_local_config(tmp_path)

        provider = create_provider(config)

        assert isinstance(provider, LocalProvider)

    def test_local_provider_is_storage_provider_instance(self, tmp_path: Path) -> None:
        """Factory-created LocalProvider is also a StorageProvider."""
        config = make_local_config(tmp_path)

        provider = create_provider(config)

        assert isinstance(provider, StorageProvider)

    def test_aws_config_raises_provider_error(self, tmp_path: Path) -> None:
        """AWS config raises ProviderError since AWS is not yet implemented."""
        config = _make_aws_config(tmp_path)

        with pytest.raises(ProviderError, match="AWS provider is not yet implemented"):
            create_provider(config)

    def test_aws_error_suggests_local_alternative(self, tmp_path: Path) -> None:
        """AWS error suggests using provider: local instead."""
        config = _make_aws_config(tmp_path)

        with pytest.raises(ProviderError, match="provider: local"):
            create_provider(config)

    def test_unknown_provider_raises_provider_error(self, tmp_path: Path) -> None:
        """An unknown provider name raises ProviderError listing supported providers."""
        storage_root = tmp_path / "feature_store"
        config = Config(
            provider="gcp",
            project_root=tmp_path,
            storage_root=storage_root,
            definitions_path=storage_root / "definitions",
            aws=None,
        )

        with pytest.raises(ProviderError, match=r"Unknown provider 'gcp'.*Supported providers: local"):
            create_provider(config)

    def test_returned_local_provider_can_write_and_read(self, tmp_path: Path) -> None:
        """Integration smoke test: factory-created provider works end-to-end."""
        config = make_local_config(tmp_path)
        provider = create_provider(config)
        data = '{"version": "1.0", "feature_groups": {}}'

        provider.write_registry(data)

        assert provider.read_registry() == data

    def test_factory_returns_distinct_instances(self, tmp_path: Path) -> None:
        """Each factory call returns a distinct provider instance."""
        config = make_local_config(tmp_path)

        p1 = create_provider(config)
        p2 = create_provider(config)

        assert p1 is not p2
