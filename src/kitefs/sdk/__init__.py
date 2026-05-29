from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

__all__ = [
    "ApplyResult",
    "FailedGroup",
    "FeatureGroupDescription",
    "FeatureGroupSummary",
    "FeatureStore",
    "FieldSpec",
    "IngestResult",
    "JoinKeySpec",
    "MaterializeResult",
    "MetadataSpec",
    "SkippedGroup",
]


def __getattr__(name: str) -> object:
    if name == "FeatureStore":
        from kitefs.sdk.feature_store import FeatureStore

        return FeatureStore
    raise AttributeError(f"module 'kitefs.sdk' has no attribute {name!r}")
