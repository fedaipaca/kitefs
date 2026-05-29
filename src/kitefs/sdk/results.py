from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

from kitefs.enums import FeatureType, StorageTarget, ValidationMode


@dataclass(frozen=True)
class ApplyResult:
    registered_groups: list[str]
    published: bool


@dataclass(frozen=True)
class FeatureGroupSummary:
    name: str
    owner: str | None
    description: str | None
    entity_key: str
    storage_target: StorageTarget
    feature_count: int


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dtype: FeatureType
    description: str | None
    expect: list[dict[str, Any]] | None


@dataclass(frozen=True)
class JoinKeySpec:
    name: str
    dtype: FeatureType
    referenced_group: str


@dataclass(frozen=True)
class MetadataSpec:
    description: str | None
    owner: str | None
    tags: dict[str, str]


@dataclass(frozen=True)
class FeatureGroupDescription:
    name: str
    storage_target: StorageTarget
    entity_key: FieldSpec
    event_timestamp: FieldSpec
    features: list[FieldSpec]
    join_keys: list[JoinKeySpec]
    ingestion_validation: ValidationMode
    offline_retrieval_validation: ValidationMode
    metadata: MetadataSpec
    applied_at: datetime.datetime | None
    last_materialized_at: datetime.datetime | None


@dataclass(frozen=True)
class ValidationFailure:
    """A single validation failure for one row and one check."""

    field: str
    constraint: str
    actual_value: Any
    entity_key_value: Any | None
    row_index: int | None


@dataclass(frozen=True)
class ValidationReport:
    """Summary of all validation results for a DataFrame.

    pass_count and fail_count count distinct rows, not individual failures.
    A row failing multiple checks is counted once in fail_count.
    """

    pass_count: int
    fail_count: int
    failures: list[ValidationFailure]


__all__ = [
    "ApplyResult",
    "FeatureGroupDescription",
    "FeatureGroupSummary",
    "FieldSpec",
    "JoinKeySpec",
    "MetadataSpec",
    "ValidationFailure",
    "ValidationReport",
]
