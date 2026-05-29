from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Satisfies type checkers without triggering a runtime import of kitefs.sdk,
    # which would break the CLI import-isolation contract.
    from kitefs.sdk.feature_store import FeatureStore
    from kitefs.sdk.results import (
        ApplyResult,
        FailedGroup,
        FeatureGroupDescription,
        FeatureGroupSummary,
        FieldSpec,
        IngestResult,
        JoinKeySpec,
        MaterializeResult,
        MetadataSpec,
        SkippedGroup,
    )

__version__ = importlib.metadata.version("kitefs")

from kitefs.definitions import (
    EntityKey,
    EventTimestamp,
    Expect,
    Feature,
    FeatureGroup,
    JoinKey,
    Metadata,
)
from kitefs.enums import FeatureType, StorageTarget, ValidationMode
from kitefs.errors import (
    ConfigurationError,
    DefinitionDiscoveryError,
    DefinitionError,
    DefinitionValidationError,
    FeatureGroupNotFoundError,
    FeatureGroupNotMaterializableError,
    IngestionShapeError,
    JoinError,
    KiteFSError,
    OfflineStoreError,
    OfflineStoreReadError,
    OfflineStoreWriteError,
    OnlineStoreError,
    OnlineStoreReadError,
    OnlineStoreWriteError,
    ProviderError,
    RegistryError,
    RegistryReadError,
    RegistryWriteError,
    RetrievalParameterError,
    ValidationError,
)

__all__ = [
    "ApplyResult",
    "ConfigurationError",
    "DefinitionDiscoveryError",
    "DefinitionError",
    "DefinitionValidationError",
    "EntityKey",
    "EventTimestamp",
    "Expect",
    "FailedGroup",
    "Feature",
    "FeatureGroup",
    "FeatureGroupDescription",
    "FeatureGroupNotFoundError",
    "FeatureGroupNotMaterializableError",
    "FeatureGroupSummary",
    "FeatureStore",
    "FeatureType",
    "FieldSpec",
    "IngestResult",
    "IngestionShapeError",
    "JoinError",
    "JoinKey",
    "JoinKeySpec",
    "KiteFSError",
    "MaterializeResult",
    "Metadata",
    "MetadataSpec",
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
    "SkippedGroup",
    "StorageTarget",
    "ValidationError",
    "ValidationMode",
    "__version__",
]


def __getattr__(name: str) -> object:
    if name == "FeatureStore":
        from kitefs.sdk import FeatureStore

        return FeatureStore
    if name in {
        "ApplyResult",
        "FailedGroup",
        "FeatureGroupDescription",
        "FeatureGroupSummary",
        "FieldSpec",
        "IngestResult",
        "JoinKeySpec",
        "MaterializeResult",
        "MetadataSpec",
        "SkippedGroup",
    }:
        import kitefs.sdk.results as _results

        return getattr(_results, name)
    raise AttributeError(f"module 'kitefs' has no attribute {name!r}")
