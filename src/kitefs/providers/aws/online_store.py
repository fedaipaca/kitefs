"""AWS DynamoDB-backed online store.

Constructors and ABC compliance only; materialize and get land in Feature 16.
"""

from __future__ import annotations

from typing import Any

import pyarrow

from kitefs.providers.base import OnlineStore


class AWSOnlineStore(OnlineStore):
    """DynamoDB-backed online store.

    Holds the resolved DynamoDB client and table prefix.
    Materialize and get operations land in Feature 16.
    """

    def __init__(self, client: Any, *, table_prefix: str) -> None:
        self._client = client
        self._table_prefix = table_prefix

    def materialize(
        self,
        feature_group: str,
        latest_rows: pyarrow.Table,
        *,
        entity_key_column: str,
        event_timestamp_column: str,
    ) -> None:
        raise NotImplementedError("AWS online materialize lands in Feature 16")

    def get(
        self,
        feature_group: str,
        entity_key_value: str | int,
        *,
        entity_key_column: str,
        select: list[str] | None,
    ) -> dict[str, Any]:
        raise NotImplementedError("AWS online get lands in Feature 16")


__all__ = ["AWSOnlineStore"]
