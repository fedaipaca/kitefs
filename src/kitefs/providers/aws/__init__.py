"""AWS provider: AWSProvider and boto3 client construction.

All boto3 and botocore imports are confined to this package.  Importing the
base kitefs package on a machine without the aws extra must not fail; boto3 is
therefore imported lazily inside _import_boto3().

Per-operation validation is deferred to the store factory methods:
- registry_store() validates remote.registry before returning a store.
- offline_store() validates remote.offline_store before returning a store.
- online_store() validates remote.online_store before returning a store.

This guarantees ConfigurationError is raised before any AWS call for every
operation that needs a store, without validating unneeded stores.
"""

from __future__ import annotations

from typing import Any

from kitefs.errors import ConfigurationError, ProviderError, format_actionable
from kitefs.providers.aws.offline_store import AWSOfflineStore
from kitefs.providers.aws.online_store import AWSOnlineStore
from kitefs.providers.aws.registry import AWSRegistryStore
from kitefs.providers.base import OfflineStore, OnlineStore, Provider, RegistryStore


def _import_boto3() -> Any:
    """Lazily import boto3; raise ProviderError when the aws extra is absent."""
    try:
        import boto3

        return boto3
    except ImportError as exc:
        raise ProviderError(
            format_actionable(
                problem="the AWS extra (boto3) is not installed",
                next_step="install it with 'pip install kitefs[aws]'",
            )
        ) from exc


def _resolve_region(remote: dict[str, Any]) -> str:
    """Return the resolved AWS region; raise ConfigurationError when absent or empty."""
    region = remote.get("region")
    if not region:
        raise ConfigurationError(
            format_actionable(
                setting="remote.region",
                problem="required field is missing or empty",
                next_step="set remote.region or KITEFS_AWS_REGION",
            )
        )
    return str(region)


def _resolve_s3_section(
    remote: dict[str, Any],
    key: str,
    label: str,
    bucket_env: str,
    prefix_env: str,
) -> tuple[str, str]:
    """Validate a registry or offline_store sub-section and return (bucket, s3_prefix).

    Args:
        remote: The resolved remote config dict.
        key: Sub-section key in remote — ``"registry"`` or ``"offline_store"``.
        label: Human-readable label for error messages — ``"registry"`` or ``"offline"``.
        bucket_env: Env-var name that sets the bucket (cited in next_step).
        prefix_env: Env-var name that sets the s3_prefix (cited in next_step).

    Raises:
        ConfigurationError: Sub-section absent, bucket empty, or s3_prefix empty.
    """
    section = remote.get(key)
    if not isinstance(section, dict):
        raise ConfigurationError(
            format_actionable(
                setting=f"remote.{key}",
                problem=f"remote {label} store is not configured",
                next_step=f"add a remote.{key} section to kitefs.yaml",
            )
        )

    bucket = section.get("bucket")
    if not bucket:
        raise ConfigurationError(
            format_actionable(
                setting=f"remote.{key}.bucket",
                problem=f"remote {label} bucket is not configured",
                next_step=f"set remote.{key}.bucket or {bucket_env}",
            )
        )

    s3_prefix = section.get("s3_prefix")
    if not s3_prefix:
        raise ConfigurationError(
            format_actionable(
                setting=f"remote.{key}.s3_prefix",
                problem=f"remote {label} S3 prefix is not configured",
                next_step=f"set remote.{key}.s3_prefix or {prefix_env}",
            )
        )

    return str(bucket), str(s3_prefix)


def _resolve_online_section(remote: dict[str, Any]) -> str:
    """Validate remote.online_store and return the DynamoDB table prefix.

    Raises:
        ConfigurationError: Sub-section absent or dynamodb_table_prefix empty.
    """
    section = remote.get("online_store")
    if not isinstance(section, dict):
        raise ConfigurationError(
            format_actionable(
                setting="remote.online_store",
                problem="remote online store is not configured",
                next_step="add a remote.online_store section to kitefs.yaml",
            )
        )

    table_prefix = section.get("dynamodb_table_prefix")
    if not table_prefix:
        raise ConfigurationError(
            format_actionable(
                setting="remote.online_store.dynamodb_table_prefix",
                problem="remote online store DynamoDB table prefix is not configured",
                next_step=(
                    "set remote.online_store.dynamodb_table_prefix or KITEFS_REMOTE_ONLINE_DYNAMODB_TABLE_PREFIX"
                ),
            )
        )

    return str(table_prefix)


class AWSProvider(Provider):
    """AWS-backed provider: S3 for registry and offline store, DynamoDB for online store.

    Construction validates the region and builds boto3 clients.  Per-store
    config validation (bucket, prefix, table prefix) is deferred to each
    factory method so that an absent store does not block unrelated operations.
    """

    def __init__(self, remote: dict[str, Any]) -> None:
        self._remote = remote

        # Import guard: raises ProviderError when the aws extra is not installed.
        boto3 = _import_boto3()

        # Region is required for client construction.
        region = _resolve_region(remote)

        try:
            self._s3 = boto3.client("s3", region_name=region)
            self._dynamodb = boto3.client("dynamodb", region_name=region)
        except Exception as exc:
            # Surface a credential-safe error — never echo access keys or tokens.
            raise ProviderError(
                format_actionable(
                    problem=f"failed to initialize AWS clients for region {region!r}",
                    next_step="check your AWS region and credentials configuration",
                )
            ) from exc

    def registry_store(self) -> RegistryStore:
        """Return an S3-backed registry store; validates registry config first."""
        bucket, s3_prefix = _resolve_s3_section(
            self._remote,
            "registry",
            "registry",
            "KITEFS_REMOTE_REGISTRY_S3_BUCKET",
            "KITEFS_REMOTE_REGISTRY_S3_PREFIX",
        )
        return AWSRegistryStore(self._s3, bucket=bucket, s3_prefix=s3_prefix)

    def offline_store(self) -> OfflineStore:
        """Return an S3-backed offline store; validates offline config first."""
        bucket, s3_prefix = _resolve_s3_section(
            self._remote,
            "offline_store",
            "offline",
            "KITEFS_REMOTE_OFFLINE_S3_BUCKET",
            "KITEFS_REMOTE_OFFLINE_S3_PREFIX",
        )
        return AWSOfflineStore(self._s3, bucket=bucket, s3_prefix=s3_prefix)

    def online_store(self) -> OnlineStore:
        """Return a DynamoDB-backed online store; validates online config first."""
        table_prefix = _resolve_online_section(self._remote)
        return AWSOnlineStore(self._dynamodb, table_prefix=table_prefix)


__all__ = [
    "AWSOfflineStore",
    "AWSOnlineStore",
    "AWSProvider",
    "AWSRegistryStore",
]
