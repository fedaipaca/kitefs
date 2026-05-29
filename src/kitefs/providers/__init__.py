"""Provider factory and remote stub.

Re-exports the provider boundary ABCs from kitefs.providers.base so callers
can import them from either location.
"""

from pathlib import Path

from kitefs.config.loader import RuntimeConfig
from kitefs.providers.base import (
    OfflineStore,
    OnlineStore,
    Provider,
    RegistryStore,
    TimestampFilter,
)


class _RemoteStubProvider(Provider):
    """Placeholder that satisfies the remote runtime target until Feature 12."""

    def registry_store(self) -> RegistryStore:
        raise NotImplementedError("AWS provider lands in Feature 12")

    def offline_store(self) -> OfflineStore:
        raise NotImplementedError("AWS provider lands in Feature 12")

    def online_store(self) -> OnlineStore:
        raise NotImplementedError("AWS provider lands in Feature 12")


def build_provider(config: RuntimeConfig, root: Path) -> Provider:
    """Construct and return the provider for the resolved runtime target."""
    if config.target == "local":
        from kitefs.providers.local import LocalProvider

        return LocalProvider(root)
    return _RemoteStubProvider()


__all__ = [
    "OfflineStore",
    "OnlineStore",
    "Provider",
    "RegistryStore",
    "TimestampFilter",
    "build_provider",
]
