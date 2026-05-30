"""Provider factory.

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


def build_provider(config: RuntimeConfig, root: Path) -> Provider:
    """Construct and return the provider for the resolved runtime target."""
    if config.target == "local":
        from kitefs.providers.local import LocalProvider

        return LocalProvider(root)

    # Lazy import keeps boto3 out of the base kitefs import path.
    from kitefs.providers.aws import AWSProvider

    return AWSProvider(config.remote or {})


def build_local_provider(root: Path) -> Provider:
    """Construct and return a local provider rooted at root.

    Use this when the local working registry must be accessed regardless of the
    configured runtime target — for example, apply() always writes the local
    working registry before any optional remote publish.
    """
    from kitefs.providers.local import LocalProvider

    return LocalProvider(root)


def build_remote_provider(config: RuntimeConfig) -> Provider:
    """Construct and return an AWS provider from the remote config section.

    Unlike build_provider, this always returns an AWSProvider regardless of
    config.target.  apply(publish=True) uses this so a producer whose target is
    'local' can still push to the remote registry.

    Raises ConfigurationError if the remote configuration is absent or invalid.
    """
    # Lazy import keeps boto3 off the base kitefs import path.
    from kitefs.providers.aws import AWSProvider

    return AWSProvider(config.remote or {})


__all__ = [
    "OfflineStore",
    "OnlineStore",
    "Provider",
    "RegistryStore",
    "TimestampFilter",
    "build_local_provider",
    "build_provider",
    "build_remote_provider",
]
