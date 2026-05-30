"""Unit tests for kitefs.providers build_provider factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kitefs.config.loader import RuntimeConfig
from kitefs.providers import build_provider
from kitefs.providers.base import OfflineStore, OnlineStore, Provider, RegistryStore
from kitefs.providers.local import LocalProvider


def _cfg(target: str) -> RuntimeConfig:
    return RuntimeConfig(version=1, project_name="test", target=target, remote=None)  # type: ignore[arg-type]


def _remote_cfg(remote: dict[str, Any] | None = None) -> RuntimeConfig:
    """Return a RuntimeConfig for remote target with a valid remote section."""
    return RuntimeConfig(
        version=1,
        project_name="test",
        target="remote",
        remote=remote
        or {
            "region": "eu-central-1",
            "registry": {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"},
            "offline_store": {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"},
            "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
        },
    )


class TestLocalTarget:
    """build_provider returns LocalProvider for target='local'."""

    def test_returns_local_provider(self, tmp_path: Path) -> None:
        """build_provider returns a LocalProvider instance for local target."""
        provider = build_provider(_cfg("local"), tmp_path)
        assert isinstance(provider, LocalProvider)

    def test_is_provider_subclass(self, tmp_path: Path) -> None:
        """LocalProvider satisfies the Provider ABC."""
        provider = build_provider(_cfg("local"), tmp_path)
        assert isinstance(provider, Provider)


class TestRemoteTarget:
    """build_provider returns AWSProvider for target='remote'."""

    def test_returns_aws_provider(self) -> None:
        """build_provider returns an AWSProvider instance for remote target."""
        from kitefs.providers.aws import AWSProvider

        provider = build_provider(_remote_cfg(), Path("."))
        assert isinstance(provider, AWSProvider)

    def test_is_provider_subclass(self) -> None:
        """AWSProvider satisfies the Provider ABC."""
        provider = build_provider(_remote_cfg(), Path("."))
        assert isinstance(provider, Provider)

    def test_not_a_local_provider(self) -> None:
        """Remote target does not return LocalProvider."""
        provider = build_provider(_remote_cfg(), Path("."))
        assert not isinstance(provider, LocalProvider)

    def test_registry_store_returns_registry_store(self) -> None:
        """AWSProvider.registry_store returns a RegistryStore instance."""
        provider = build_provider(_remote_cfg(), Path("."))
        assert isinstance(provider.registry_store(), RegistryStore)

    def test_offline_store_returns_offline_store(self) -> None:
        """AWSProvider.offline_store returns an OfflineStore instance."""
        provider = build_provider(_remote_cfg(), Path("."))
        assert isinstance(provider.offline_store(), OfflineStore)

    def test_online_store_returns_online_store(self) -> None:
        """AWSProvider.online_store returns an OnlineStore instance."""
        provider = build_provider(_remote_cfg(), Path("."))
        assert isinstance(provider.online_store(), OnlineStore)


class TestLocalProviderStubs:
    """LocalProvider returns implemented stores for offline, registry, and online."""

    def test_offline_store_returns_offline_store_instance(self, tmp_path: Path) -> None:
        """LocalProvider.offline_store returns an OfflineStore instance."""
        provider = build_provider(_cfg("local"), tmp_path)
        assert isinstance(provider.offline_store(), OfflineStore)

    def test_online_store_returns_online_store_instance(self, tmp_path: Path) -> None:
        """LocalProvider.online_store returns an OnlineStore instance."""
        provider = build_provider(_cfg("local"), tmp_path)
        assert isinstance(provider.online_store(), OnlineStore)

    def test_registry_store_returns_registry_store(self, tmp_path: Path) -> None:
        """LocalProvider.registry_store returns a RegistryStore instance."""
        provider = build_provider(_cfg("local"), tmp_path)
        assert isinstance(provider.registry_store(), RegistryStore)
