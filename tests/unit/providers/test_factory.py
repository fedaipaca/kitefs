"""Unit tests for kitefs.providers build_provider factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from kitefs.config.loader import RuntimeConfig
from kitefs.providers import build_provider
from kitefs.providers.base import Provider, RegistryStore
from kitefs.providers.local import LocalProvider


def _cfg(target: str) -> RuntimeConfig:
    return RuntimeConfig(version=1, project_name="test", target=target, remote=None)  # type: ignore[arg-type]


class TestLocalTarget:
    """build_provider returns LocalProvider for target='local'."""

    def test_returns_local_provider(self, tmp_path) -> None:
        """build_provider returns a LocalProvider instance for local target."""
        provider = build_provider(_cfg("local"), tmp_path)
        assert isinstance(provider, LocalProvider)

    def test_is_provider_subclass(self, tmp_path) -> None:
        """LocalProvider satisfies the Provider ABC."""
        provider = build_provider(_cfg("local"), tmp_path)
        assert isinstance(provider, Provider)


class TestRemoteTarget:
    """build_provider returns a stub Provider for target='remote'."""

    def test_returns_a_provider(self) -> None:
        """build_provider returns a Provider instance for remote target."""
        provider = build_provider(_cfg("remote"), Path("."))
        assert isinstance(provider, Provider)

    def test_not_a_local_provider(self) -> None:
        """Remote target does not return LocalProvider."""
        provider = build_provider(_cfg("remote"), Path("."))
        assert not isinstance(provider, LocalProvider)

    def test_registry_store_raises(self) -> None:
        """Remote stub's registry_store raises NotImplementedError."""
        provider = build_provider(_cfg("remote"), Path("."))
        with pytest.raises(NotImplementedError):
            provider.registry_store()

    def test_offline_store_raises(self) -> None:
        """Remote stub's offline_store raises NotImplementedError."""
        provider = build_provider(_cfg("remote"), Path("."))
        with pytest.raises(NotImplementedError):
            provider.offline_store()

    def test_online_store_raises(self) -> None:
        """Remote stub's online_store raises NotImplementedError."""
        provider = build_provider(_cfg("remote"), Path("."))
        with pytest.raises(NotImplementedError):
            provider.online_store()


class TestLocalProviderStubs:
    """LocalProvider raises NotImplementedError for offline and online stores."""

    def test_offline_store_raises(self, tmp_path) -> None:
        """LocalProvider.offline_store raises NotImplementedError."""
        provider = build_provider(_cfg("local"), tmp_path)
        with pytest.raises(NotImplementedError):
            provider.offline_store()

    def test_online_store_raises(self, tmp_path) -> None:
        """LocalProvider.online_store raises NotImplementedError."""
        provider = build_provider(_cfg("local"), tmp_path)
        with pytest.raises(NotImplementedError):
            provider.online_store()

    def test_registry_store_returns_registry_store(self, tmp_path) -> None:
        """LocalProvider.registry_store returns a RegistryStore instance."""
        provider = build_provider(_cfg("local"), tmp_path)
        assert isinstance(provider.registry_store(), RegistryStore)
