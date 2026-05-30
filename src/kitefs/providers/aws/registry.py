"""AWS S3-backed registry store.

Constructors and ABC compliance only; read/write methods land in Feature 14.
"""

from __future__ import annotations

from typing import Any

from kitefs.providers.base import RegistryStore


class AWSRegistryStore(RegistryStore):
    """S3-backed registry store.

    Holds the resolved S3 client and coordinates (bucket, key).
    Read and write operations land in Feature 14.
    """

    def __init__(self, client: Any, *, bucket: str, s3_prefix: str) -> None:
        self._client = client
        self._bucket = bucket
        self._s3_prefix = s3_prefix
        # Canonical registry key: <prefix>/registry.json
        self._key = f"{s3_prefix}/registry.json"

    def read(self) -> dict[str, Any]:
        raise NotImplementedError("AWS registry read lands in Feature 14")

    def write(self, document: dict[str, Any]) -> None:
        raise NotImplementedError("AWS registry write lands in Feature 14")


__all__ = ["AWSRegistryStore"]
