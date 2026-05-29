"""Provider boundary ABCs and TimestampFilter value object.

These contracts are stable across local and AWS provider implementations.
Internal modules import from this module: `from kitefs.providers.base import ...`
"""

from __future__ import annotations

import abc
import datetime
from dataclasses import dataclass
from typing import Any

import pyarrow


@dataclass(frozen=True)
class TimestampFilter:
    """Half-open or closed time bounds for offline store reads."""

    gt: datetime.datetime | None = None
    gte: datetime.datetime | None = None
    lt: datetime.datetime | None = None
    lte: datetime.datetime | None = None


class RegistryStore(abc.ABC):
    """Read and write the registry document."""

    @abc.abstractmethod
    def read(self) -> dict[str, Any]: ...

    @abc.abstractmethod
    def write(self, document: dict[str, Any]) -> None: ...


class OfflineStore(abc.ABC):
    """Write and read partitioned offline feature data."""

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
    """Materialize and serve online feature values."""

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
    """Unified entry point for all storage backends."""

    @abc.abstractmethod
    def registry_store(self) -> RegistryStore: ...

    @abc.abstractmethod
    def offline_store(self) -> OfflineStore: ...

    @abc.abstractmethod
    def online_store(self) -> OnlineStore: ...


__all__ = [
    "OfflineStore",
    "OnlineStore",
    "Provider",
    "RegistryStore",
    "TimestampFilter",
]
