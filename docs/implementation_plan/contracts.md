This file defines the core data types, enums, exceptions, provider interfaces, and the main SDK class for the KiteFS feature store, specifying the contracts and structures used throughout the library.

```python
import abc
import datetime
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas
import pyarrow


# --- ENUMS ---

class FeatureType(Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    DATETIME = "DATETIME"

class StorageTarget(Enum):
    OFFLINE = "OFFLINE"
    OFFLINE_AND_ONLINE = "OFFLINE_AND_ONLINE"

class ValidationMode(Enum):
    ERROR = "ERROR"
    FILTER = "FILTER"
    NONE = "NONE"



# --- DEFINITION TYPES ---

class Expect:
    def __init__(self) -> None: ...
    def not_null(self) -> Expect: ...
    def gt(self, value: int | float | datetime.datetime) -> Expect: ...
    def gte(self, value: int | float | datetime.datetime) -> Expect: ...
    def lt(self, value: int | float | datetime.datetime) -> Expect: ...
    def lte(self, value: int | float | datetime.datetime) -> Expect: ...
    def is_in(self, values: list[str | int | float | datetime.datetime]) -> Expect: ...


class EntityKey:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        description: str | None = None,
    ) -> None: ...


class EventTimestamp:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType = FeatureType.DATETIME,
        description: str | None = None,
    ) -> None: ...


class Feature:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        description: str | None = None,
        expect: Expect | None = None,
    ) -> None: ...


class JoinKey:
    def __init__(
        self,
        *,
        name: str,
        dtype: FeatureType,
        referenced_group: str,
        description: str | None = None,
    ) -> None: ...


class Metadata:
    def __init__(
        self,
        *,
        description: str,
        owner: str,
        tags: dict[str, str] | None = None,
    ) -> None: ...


class FeatureGroup:
    def __init__(
        self,
        *,
        name: str,
        storage_target: StorageTarget,
        entity_key: EntityKey,
        event_timestamp: EventTimestamp,
        features: list[Feature],
        join_keys: list[JoinKey] | None = None,
        ingestion_validation: ValidationMode = ValidationMode.ERROR,
        offline_retrieval_validation: ValidationMode = ValidationMode.NONE,
        metadata: Metadata | None = None,
    ) -> None: ...


# --- RETURN TYPES ---

@dataclass(frozen=True)
class ApplyResult:
    registered_groups: list[str]
    published: bool


@dataclass(frozen=True)
class PullResult:
    """Post-MVP."""


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
    field: str
    constraint: str
    actual_value: Any
    entity_key_value: Any | None
    row_index: int | None


@dataclass(frozen=True)
class ValidationReport:
    pass_count: int
    fail_count: int
    failures: list[ValidationFailure]


@dataclass(frozen=True)
class IngestResult:
    feature_group: str
    accepted_rows: int
    rejected_rows: int
    written_files: list[str]
    validation_report: ValidationReport | None


@dataclass(frozen=True)
class SkippedGroup:
    name: str
    reason: str

@dataclass(frozen=True)
class FailedGroup:
    name: str
    error_message: str

@dataclass(frozen=True)
class MaterializeResult:
    succeeded: list[str]
    skipped: list[SkippedGroup]
    failed: list[FailedGroup]


# --- EXCEPTIONS ---

class KiteFSError(Exception): ...

class ConfigurationError(KiteFSError): ...
class DefinitionError(KiteFSError): ...
class DefinitionDiscoveryError(KiteFSError): ...
class DefinitionValidationError(KiteFSError): ...

class RegistryError(KiteFSError): ...
class RegistryReadError(RegistryError): ...
class RegistryWriteError(RegistryError): ...

class FeatureGroupNotFoundError(KiteFSError): ...
class FeatureGroupNotMaterializableError(KiteFSError): ...

class ValidationError(KiteFSError):
    report: ValidationReport

class IngestionShapeError(KiteFSError): ...
class RetrievalParameterError(KiteFSError): ...
class JoinError(KiteFSError): ...

class OfflineStoreError(KiteFSError): ...
class OfflineStoreReadError(OfflineStoreError): ...
class OfflineStoreWriteError(OfflineStoreError): ...

class OnlineStoreError(KiteFSError): ...
class OnlineStoreReadError(OnlineStoreError): ...
class OnlineStoreWriteError(OnlineStoreError): ...

class ProviderError(KiteFSError): ...


# --- INTERNAL PROVIDERS ---

@dataclass(frozen=True)
class TimestampFilter:
    gt: datetime.datetime | None = None
    gte: datetime.datetime | None = None
    lt: datetime.datetime | None = None
    lte: datetime.datetime | None = None


class RegistryStore(abc.ABC):
    @abc.abstractmethod
    def read(self) -> dict[str, Any]: ...

    @abc.abstractmethod
    def write(self, document: dict[str, Any]) -> None: ...


class OfflineStore(abc.ABC):
    @abc.abstractmethod
    def write(
        self,
        feature_group: str,
        data: pyarrow.Table,
        *,
        event_timestamp_column: str,
        source_prefix: str,
    ) -> list[str]: ...

    @abc.abstractmethod
    def read(
        self,
        feature_group: str,
        *,
        event_timestamp_column: str,
        schema: pyarrow.Schema,
        timestamp_filter: TimestampFilter | None = None,
    ) -> pyarrow.Table: ...


class OnlineStore(abc.ABC):
    @abc.abstractmethod
    def materialize(
        self,
        feature_group: str,
        latest_rows: pyarrow.Table,
        *,
        entity_key_column: str,
    ) -> None: ...

    @abc.abstractmethod
    def get(
        self,
        feature_group: str,
        entity_key_value: str | int,
        *,
        entity_key_column: str,
        select: list[str] | None,
    ) -> dict[str, Any]: ...


class Provider(abc.ABC):
    @abc.abstractmethod
    def registry_store(self) -> RegistryStore: ...

    @abc.abstractmethod
    def offline_store(self) -> OfflineStore: ...

    @abc.abstractmethod
    def online_store(self) -> OnlineStore: ...


# --- PUBLIC SDK ---

class FeatureStore:
    def __init__(self) -> None: ...

    def apply(self, *, publish: bool = False) -> ApplyResult: ...

    def pull(self) -> PullResult: ...

    def list_feature_groups(self) -> list[FeatureGroupSummary]: ...

    def describe_feature_group(self, name: str) -> FeatureGroupDescription: ...

    def ingest(
        self,
        feature_group: str,
        data: pandas.DataFrame | str | os.PathLike[str],
    ) -> IngestResult: ...

    def get_historical_features(
        self,
        *,
        from_: str,
        select: list[str] | dict[str, list[str]],
        join: list[str] | None = None,
        where: dict[str, dict[str, datetime.datetime]] | None = None,
    ) -> pandas.DataFrame: ...
        # Information about `select`:
        #
        # select is required.
        #
        # "*" must always be passed inside a list.
        #
        # Without join:
        #   - Use a flat list of feature field names:
        #       select=["net_area", "sold_price"]
        #   - Use ["*"] to select all feature fields from the base group:
        #       select=["*"]
        #
        # With join:
        #   - Use a dict keyed by feature group name.
        #   - Each dict value must be a list of feature field names or ["*"]:
        #       select={
        #           "listing_features": ["net_area", "sold_price"],
        #           "town_market_features": ["avg_price_per_sqm"],
        #       }
        #       select={
        #           "listing_features": ["*"],
        #           "town_market_features": ["*"],
        #       }
        #
        # "*" means all feature fields for that group.
        # "*" must be the only item in its list.
        # Lists such as ["*", "net_area"] are invalid and raise RetrievalParameterError.
        #
        # Structural fields are always returned automatically and must not be included
        # in select: entity key, event timestamp, and join key.

    def materialize(
        self,
        feature_group: str | None = None,
    ) -> MaterializeResult: ...

    def get_online_features(
        self,
        *,
        from_: str,
        select: list[str],
        where: dict[str, dict[str, str | int]],
    ) -> dict[str, Any]: ...
        # Information about `select`:
        #
        # select is required.
        #
        # "*" must always be passed inside a list.
        #
        # Use a list of feature field names to retrieve specific online features:
        #   select=["avg_price_per_sqm"]
        #
        # Use ["*"] to retrieve all online feature fields for the group:
        #   select=["*"]
        #
        # "*" means all feature fields for the requested online feature group.
        # "*" must be the only item in the list.
        # Lists such as ["*", "avg_price_per_sqm"] are invalid and raise RetrievalParameterError.
        #
        # Structural fields are always returned automatically and must not be included
        # in select: entity key and event timestamp.
        #
        # where must identify exactly one entity key using eq:
        #   where={"town_id": {"eq": 1}}
        #
        # Only one entity key lookup is supported for MVP.

```
