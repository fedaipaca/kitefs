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


@dataclass(frozen=True)
class IngestResult:
    """Summary of a completed ingest() call.

    accepted_rows: number of rows written to the offline store.
    rejected_rows: number of rows dropped by FILTER mode or excluded before writing.
    written_files: absolute paths of Parquet files created. Empty when accepted_rows == 0.
    validation_report: None when ingestion_validation is NONE; otherwise the ValidationReport
        produced by the validation engine.
    """

    feature_group: str
    accepted_rows: int
    rejected_rows: int
    written_files: list[str]
    validation_report: ValidationReport | None


@dataclass(frozen=True)
class SkippedGroup:
    """A group excluded from materialization because it had no offline data."""

    name: str
    reason: str  # human-readable, e.g. "no offline data"


@dataclass(frozen=True)
class FailedGroup:
    """A group that failed during materialization due to a provider write error."""

    name: str
    error_message: str


@dataclass(frozen=True)
class MaterializeResult:
    """Per-group outcome summary returned by FeatureStore.materialize().

    succeeded: names of groups whose online table was fully replaced.
    skipped: groups excluded because they had no offline rows.
    failed: groups that encountered a provider write error.
    """

    succeeded: list[str]
    skipped: list[SkippedGroup]
    failed: list[FailedGroup]


__all__ = [
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
    "ValidationFailure",
    "ValidationReport",
]
