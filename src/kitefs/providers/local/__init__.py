from pathlib import Path

from kitefs.providers.base import OfflineStore, OnlineStore, Provider, RegistryStore
from kitefs.providers.local.registry import LocalRegistryStore


class LocalProvider(Provider):
    """Local filesystem-backed provider."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def registry_store(self) -> RegistryStore:
        return LocalRegistryStore(self._root)

    def offline_store(self) -> OfflineStore:
        raise NotImplementedError("Local offline store lands in Feature 4")

    def online_store(self) -> OnlineStore:
        raise NotImplementedError("Local online store lands in Feature 5")


__all__ = ["LocalProvider"]
