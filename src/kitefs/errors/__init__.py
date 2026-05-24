from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kitefs.sdk.results import ValidationReport  # type: ignore[import]


class KiteFSError(Exception):
    pass


class ConfigurationError(KiteFSError):
    pass


class DefinitionError(KiteFSError):
    pass


class DefinitionDiscoveryError(KiteFSError):
    pass


class DefinitionValidationError(KiteFSError):
    pass


class RegistryError(KiteFSError):
    pass


class RegistryReadError(RegistryError):
    pass


class RegistryWriteError(RegistryError):
    pass


class FeatureGroupNotFoundError(KiteFSError):
    pass


class FeatureGroupNotMaterializableError(KiteFSError):
    pass


class ValidationError(KiteFSError):
    report: ValidationReport

    def __init__(self, message: str, *, report: ValidationReport | Any = None) -> None:
        super().__init__(message)
        self.report = report


class IngestionShapeError(KiteFSError):
    pass


class RetrievalParameterError(KiteFSError):
    pass


class JoinError(KiteFSError):
    pass


class OfflineStoreError(KiteFSError):
    pass


class OfflineStoreReadError(OfflineStoreError):
    pass


class OfflineStoreWriteError(OfflineStoreError):
    pass


class OnlineStoreError(KiteFSError):
    pass


class OnlineStoreReadError(OnlineStoreError):
    pass


class OnlineStoreWriteError(OnlineStoreError):
    pass


class ProviderError(KiteFSError):
    pass


def format_actionable(
    *,
    setting: str | None = None,
    group: str | None = None,
    field: str | None = None,
    problem: str,
    next_step: str,
) -> str:
    parts = []
    if setting is not None:
        parts.append(f"setting={setting}")
    if group is not None:
        parts.append(f"group={group}")
    if field is not None:
        parts.append(f"field={field}")
    context = " ".join(parts)
    prefix = f"{context}: " if context else ""
    return f"{prefix}{problem}. Next: {next_step}"


__all__ = [
    "ConfigurationError",
    "DefinitionDiscoveryError",
    "DefinitionError",
    "DefinitionValidationError",
    "FeatureGroupNotFoundError",
    "FeatureGroupNotMaterializableError",
    "IngestionShapeError",
    "JoinError",
    "KiteFSError",
    "OfflineStoreError",
    "OfflineStoreReadError",
    "OfflineStoreWriteError",
    "OnlineStoreError",
    "OnlineStoreReadError",
    "OnlineStoreWriteError",
    "ProviderError",
    "RegistryError",
    "RegistryReadError",
    "RegistryWriteError",
    "RetrievalParameterError",
    "ValidationError",
    "format_actionable",
]
