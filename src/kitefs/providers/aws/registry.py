"""AWS S3-backed registry store."""

from __future__ import annotations

import json
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from kitefs.errors import RegistryReadError, RegistryWriteError
from kitefs.providers.base import RegistryStore
from kitefs.registry.serializer import serialize_registry_document


class AWSRegistryStore(RegistryStore):
    """S3-backed registry store.

    Reads and writes the registry JSON document at ``s3://{bucket}/{s3_prefix}/registry.json``
    using a pre-constructed boto3 S3 client.  The serialized bytes are byte-identical to the
    local registry store so a consumer's remote read produces the same document a producer's
    local write produced.
    """

    def __init__(self, client: Any, *, bucket: str, s3_prefix: str) -> None:
        self._client = client
        self._bucket = bucket
        self._s3_prefix = s3_prefix
        # Canonical registry key: <prefix>/registry.json
        self._key = f"{s3_prefix}/registry.json"

    def read(self) -> dict[str, Any]:
        """Fetch and parse the registry document from S3.

        Raises:
            RegistryReadError: Object absent, network failure, or malformed/invalid document.
        """
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=self._key)
            document = json.loads(response["Body"].read())
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404"}:
                raise RegistryReadError(
                    f"Remote registry not found at s3://{self._bucket}/{self._key}. "
                    "Run 'kitefs apply --publish' to publish the registry."
                ) from exc
            if code == "NoSuchBucket":
                raise RegistryReadError(
                    f"Remote registry bucket '{self._bucket}' does not exist or is inaccessible. "
                    "Check or create the bucket and verify remote.registry.bucket in kitefs.yaml."
                ) from exc
            raise RegistryReadError(
                f"Failed to read remote registry at s3://{self._bucket}/{self._key}: {exc}. "
                "Check region, bucket/prefix, credentials, and S3 permissions."
            ) from exc
        except BotoCoreError as exc:
            raise RegistryReadError(
                f"Failed to read remote registry at s3://{self._bucket}/{self._key}: {exc}. "
                "Check region, credentials, and S3 connectivity."
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RegistryReadError(
                f"Remote registry at s3://{self._bucket}/{self._key} could not be parsed: {exc}"
            ) from exc

        if not isinstance(document, dict):
            raise RegistryReadError(
                f"Remote registry at s3://{self._bucket}/{self._key} has an unexpected format: expected a JSON object"
            )
        if not isinstance(document.get("feature_groups"), dict):
            raise RegistryReadError(
                f"Remote registry at s3://{self._bucket}/{self._key} is corrupt:"
                " missing or invalid 'feature_groups' field"
            )
        return document  # type: ignore[return-value]

    def write(self, document: dict[str, Any]) -> None:
        """Serialize and upload the registry document to S3 via a single PutObject call.

        The serialized bytes are byte-identical to those written by LocalRegistryStore
        (sort_keys=True, indent=2, ensure_ascii=False, trailing newline).

        Raises:
            RegistryWriteError: PutObject failed.
        """
        body = serialize_registry_document(document).encode("utf-8")
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=self._key,
                Body=body,
                ContentType="application/json",
            )
        except (ClientError, BotoCoreError) as exc:
            raise RegistryWriteError(
                f"Failed to write remote registry at s3://{self._bucket}/{self._key}: {exc}. "
                "Check bucket/prefix, region, credentials, and S3 write permissions."
            ) from exc


__all__ = ["AWSRegistryStore"]
