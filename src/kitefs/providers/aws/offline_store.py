"""AWS S3-backed offline store.

Constructors and ABC compliance only; write lands in Feature 14, read in Feature 15.
"""

from __future__ import annotations

from typing import Any

import pyarrow

from kitefs.providers.base import OfflineStore, TimestampFilter


class AWSOfflineStore(OfflineStore):
    """S3-backed offline store.

    Holds the resolved S3 client and coordinates (bucket, s3_prefix).
    Write lands in Feature 14; read lands in Feature 15.
    """

    def __init__(self, client: Any, *, bucket: str, s3_prefix: str) -> None:
        self._client = client
        self._bucket = bucket
        self._s3_prefix = s3_prefix

    def write(
        self,
        feature_group: str,
        data: pyarrow.Table,
        *,
        event_timestamp_column: str,
        source_prefix: str,
    ) -> list[str]:
        raise NotImplementedError("AWS offline write lands in Feature 14")

    def read(
        self,
        feature_group: str,
        *,
        event_timestamp_column: str,
        schema: pyarrow.Schema,
        timestamp_filter: TimestampFilter | None = None,
    ) -> pyarrow.Table:
        raise NotImplementedError("AWS offline read lands in Feature 15")


__all__ = ["AWSOfflineStore"]
