from pathlib import Path

from kitefs.providers.base import OfflineStore, OnlineStore, Provider, RegistryStore
from kitefs.providers.local.offline_store import LocalOfflineStore
from kitefs.providers.local.online_store import LocalOnlineStore
from kitefs.providers.local.registry import LocalRegistryStore


class LocalProvider(Provider):
    """Local filesystem-backed provider."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def registry_store(self) -> RegistryStore:
        return LocalRegistryStore(self._root)

    def offline_store(self) -> OfflineStore:
        return LocalOfflineStore(self._root)

    def online_store(self) -> OnlineStore:
        return LocalOnlineStore(self._root)


__all__ = ["LocalProvider"]
