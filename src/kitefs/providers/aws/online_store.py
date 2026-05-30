"""AWS DynamoDB-backed online store.

One DynamoDB table per online-capable feature group, named:
    {table_prefix}{group_name}

Materialization:
    1. Lazily creates the table (or validates the existing schema) via
       DescribeTable / CreateTable with PAY_PER_REQUEST billing.
    2. Writes all latest rows in BatchWriteItem chunks of up to 25 items.
    3. Retries UnprocessedItems once after a short delay; persists failures
       as OnlineStoreWriteError so the SDK can record the group as failed.

Reads:
    GetItem keyed by entity key value.  Returns {} on miss or missing table.
    DATETIME values are returned as ISO-8601 UTC strings so _coerce_online_result
    in the SDK can parse them back to UTC-aware datetime objects.

Type mapping:
    INTEGER / FLOAT  → DynamoDB N
    STRING / DATETIME → DynamoDB S  (DATETIME serialized as YYYY-MM-DDTHH:MM:SS.ffffffZ)

Numbers are stored and returned as strings (DynamoDB N type); _deserialize_attr
converts them to int/float.  Whole-valued FLOATs (e.g. 15200.0) arrive as int
from _deserialize_attr; the SDK's _coerce_online_result restores the declared
float dtype using the registry description.

Null / absent attributes:
    None values are omitted from the item on write (DynamoDB null representation
    per Behavior #5 of the feature spec).  On read, columns absent from the
    stored item are returned as None by get() so the SDK result shape is
    consistent with the local SQLite provider.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pyarrow as pa
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, PartialCredentialsError

from kitefs.constants import DATETIME_FMT
from kitefs.errors import OnlineStoreReadError, OnlineStoreWriteError, ProviderError, format_actionable
from kitefs.providers.base import OnlineStore

# Delay in seconds before the single UnprocessedItems retry.
# Set to 0 in tests via monkeypatch.
_UNPROCESSED_RETRY_DELAY_SECONDS = 0.2


# ---------------------------------------------------------------------------
# DynamoDB attribute helpers
# ---------------------------------------------------------------------------


def _attr_type_for_arrow(arrow_type: pa.DataType) -> str:
    """Return the DynamoDB attribute type string ("N" or "S") for an Arrow type.

    INTEGER / FLOAT → "N" (DynamoDB Number)
    STRING / DATETIME (timestamp) → "S" (DynamoDB String)
    """
    if pa.types.is_integer(arrow_type) or pa.types.is_floating(arrow_type):
        return "N"
    return "S"


def _serialize_attr(value: Any, arrow_type: pa.DataType) -> dict[str, str] | None:
    """Convert a Python value to a DynamoDB attribute value dict, or None to omit.

    Returns None for None (caller skips the attribute — DynamoDB null representation).

    DATETIME (PyArrow timestamp) → ISO-8601 UTC string → {"S": "YYYY-MM-DDTHH:MM:SS.ffffffZ"}
    Numeric types → {"N": str(value)}
    String / fallback → {"S": str(value)}
    """
    if value is None:
        return None

    if pa.types.is_timestamp(arrow_type):
        # Normalize to a datetime; pandas Timestamps are accepted here.
        if not isinstance(value, datetime):
            import pandas as pd

            value = pd.Timestamp(value).to_pydatetime()
        # Treat naive as UTC per the datetime contract.
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return {"S": value.strftime(DATETIME_FMT)}

    if pa.types.is_integer(arrow_type) or pa.types.is_floating(arrow_type):
        return {"N": str(value)}

    return {"S": str(value)}


def _deserialize_attr(av: dict[str, Any]) -> Any:
    """Convert a DynamoDB attribute value dict to a Python scalar.

    "S" → str
    "N" → int when the string represents a whole number, float otherwise
    "NULL" → None
    Other / unknown → pass the value through unchanged.
    """
    if "S" in av:
        return av["S"]
    if "N" in av:
        d = Decimal(av["N"])
        return int(d) if d == d.to_integral_value() else float(d)
    if "NULL" in av:
        return None
    # Unexpected type — return raw dict so callers are not silently broken.
    return av


# ---------------------------------------------------------------------------
# AWSOnlineStore
# ---------------------------------------------------------------------------


class AWSOnlineStore(OnlineStore):
    """DynamoDB-backed online store for remote deployments.

    All DynamoDB I/O uses the supplied boto3 client.  boto3 and botocore are
    never imported in packages outside providers/aws/.
    """

    def __init__(self, client: Any, *, table_prefix: str) -> None:
        self._client = client
        self._table_prefix = table_prefix

    # ------------------------------------------------------------------
    # Public ABC implementation
    # ------------------------------------------------------------------

    def materialize(
        self,
        feature_group: str,
        latest_rows: pa.Table,
        *,
        entity_key_column: str,
        event_timestamp_column: str,
    ) -> None:
        """Write *latest_rows* to the DynamoDB table for *feature_group*.

        Lazily creates the table if it does not yet exist, validates the
        partition key schema if it does, then writes all items in BatchWriteItem
        chunks of at most 25.  UnprocessedItems are retried once.

        On any failure (table schema mismatch, write error, credential error)
        a typed KiteFS exception is raised.  The SDK wraps the exception into a
        FailedGroup and continues; partial items already written may remain in
        the table and will be overwritten on the next successful materialize run.

        Args:
            feature_group: Registry name of the feature group.
            latest_rows: PyArrow table with one row per entity key (output of
                select_latest_rows); columns include entity key, event timestamp,
                any join keys, and feature columns.
            entity_key_column: Name of the partition-key column.
            event_timestamp_column: Name of the event-timestamp column
                (informational; not treated specially during write).
        """
        table_name = f"{self._table_prefix}{feature_group}"
        schema = latest_rows.schema
        key_arrow_type = schema.field(entity_key_column).type
        key_attr_type = _attr_type_for_arrow(key_arrow_type)

        try:
            self._ensure_table(table_name, feature_group, entity_key_column, key_attr_type)
        except (OnlineStoreWriteError, ProviderError):
            raise
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise ProviderError(
                format_actionable(
                    problem="AWS credentials are missing or invalid for DynamoDB table setup",
                    next_step="check your AWS credentials and DynamoDB permissions",
                )
            ) from exc
        except (ClientError, BotoCoreError) as exc:
            raise OnlineStoreWriteError(
                format_actionable(
                    group=feature_group,
                    problem=f"failed to ensure DynamoDB table {table_name!r}: {exc}",
                    next_step="check your DynamoDB table configuration and AWS permissions",
                )
            ) from exc

        # Serialize rows to DynamoDB wire format.
        n_cols = len(schema)
        col_arrays = [latest_rows.column(i).to_pylist() for i in range(n_cols)]
        items: list[dict[str, Any]] = []
        for row_idx in range(len(latest_rows)):
            item: dict[str, Any] = {}
            for col_idx in range(n_cols):
                field = schema.field(col_idx)
                raw = col_arrays[col_idx][row_idx]
                av = _serialize_attr(raw, field.type)
                if av is not None:
                    item[field.name] = av
            items.append(item)

        try:
            self._batch_write(table_name, feature_group, items)
        except (OnlineStoreWriteError, ProviderError):
            raise
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise ProviderError(
                format_actionable(
                    problem="AWS credentials are missing or invalid for DynamoDB write",
                    next_step="check your AWS credentials and DynamoDB write permissions",
                )
            ) from exc
        except (ClientError, BotoCoreError) as exc:
            raise OnlineStoreWriteError(
                format_actionable(
                    group=feature_group,
                    problem=f"DynamoDB write failed for table {table_name!r}: {exc}",
                    next_step="check your DynamoDB table, region, credentials, and write permissions",
                )
            ) from exc

    def get(
        self,
        feature_group: str,
        entity_key_value: str | int,
        *,
        entity_key_column: str,
        select: list[str] | None,
    ) -> dict[str, Any]:
        """Return the stored online row for *entity_key_value*, or {} on miss.

        Issues a single GetItem lookup against the group's DynamoDB table.
        Returns {} when the table has never been materialized (ResourceNotFoundException)
        or when no item matches the entity key (miss).

        The returned dict contains all stored attributes, projected to *select*
        when provided.  Attributes absent from the stored item (null features)
        are returned as None so the result shape matches the local provider.
        DATETIME values are ISO-8601 UTC strings (YYYY-MM-DDTHH:MM:SS.ffffffZ)
        so the SDK's _coerce_online_result can parse them to UTC-aware datetimes.

        Args:
            feature_group: Registry name of the feature group.
            entity_key_value: Entity key lookup value (int for INTEGER keys,
                str for STRING keys).
            entity_key_column: Name of the partition-key column.
            select: Column names to return; None means return all stored columns.

        Returns:
            Dict of column → value on hit; {} on miss or missing table.

        Raises:
            OnlineStoreReadError: GetItem failed for reasons other than a
                missing item or missing table.  The error message contains the
                underlying AWS error code so the caller can act on it.

        Note on error handling divergence: unlike the offline store, any
        ClientError (including AccessDenied) raises OnlineStoreReadError rather
        than ProviderError.  This matches the Feature 16 BDD requirement that
        read failures — including auth failures — surface as OnlineStoreReadError
        with the AWS error code visible.  Only botocore-level
        NoCredentialsError / PartialCredentialsError map to ProviderError.
        """
        table_name = f"{self._table_prefix}{feature_group}"
        key_attr_type = "N" if isinstance(entity_key_value, int) else "S"
        key = {entity_key_column: {key_attr_type: str(entity_key_value)}}

        try:
            resp = self._client.get_item(TableName=table_name, Key=key)
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise ProviderError(
                format_actionable(
                    problem="AWS credentials are missing or invalid for DynamoDB read",
                    next_step="check your AWS credentials and DynamoDB read permissions",
                )
            ) from exc
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                # Table was never created (group never materialized).
                return {}
            # All other ClientErrors — including AccessDenied — surface as
            # OnlineStoreReadError so the caller can see the error code.
            raise OnlineStoreReadError(
                format_actionable(
                    group=feature_group,
                    problem=f"DynamoDB GetItem failed for table {table_name!r}: {exc}",
                    next_step="check your DynamoDB table, region, credentials, and read permissions",
                )
            ) from exc
        except BotoCoreError as exc:
            raise OnlineStoreReadError(
                format_actionable(
                    group=feature_group,
                    problem=f"DynamoDB GetItem failed for table {table_name!r}: {exc}",
                    next_step="check region, credentials, and DynamoDB connectivity",
                )
            ) from exc

        item = resp.get("Item")
        if not item:
            return {}

        data = {name: _deserialize_attr(av) for name, av in item.items()}
        if select is None:
            return data
        # Use .get() so columns absent from the stored item (null features) come
        # back as None rather than being silently dropped — consistent with the
        # local SQLite provider.
        return {col: data.get(col) for col in select}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_table(
        self,
        table_name: str,
        feature_group: str,
        entity_key_column: str,
        key_attr_type: str,
    ) -> None:
        """Create the DynamoDB table or validate the schema of an existing one.

        - If the table does not exist: create it with PAY_PER_REQUEST billing and
          wait until it reaches the ACTIVE state.
        - If the table exists: verify it has exactly one HASH key (no RANGE key),
          its AttributeName matches entity_key_column, and its AttributeType
          matches key_attr_type.  Raise OnlineStoreWriteError on any mismatch.

        Raises ClientError / BotoCoreError — callers wrap those into domain errors.
        """
        try:
            resp = self._client.describe_table(TableName=table_name)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
                raise
            # Table does not exist — create it.
            self._client.create_table(
                TableName=table_name,
                KeySchema=[{"AttributeName": entity_key_column, "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": entity_key_column, "AttributeType": key_attr_type}],
                BillingMode="PAY_PER_REQUEST",
            )
            self._client.get_waiter("table_exists").wait(TableName=table_name)
            return

        # Table exists — validate the key schema.
        table_desc = resp["Table"]
        key_schema = table_desc.get("KeySchema", [])
        attr_defs = {a["AttributeName"]: a["AttributeType"] for a in table_desc.get("AttributeDefinitions", [])}

        hash_keys = [k for k in key_schema if k["KeyType"] == "HASH"]
        range_keys = [k for k in key_schema if k["KeyType"] == "RANGE"]

        if range_keys or len(hash_keys) != 1:
            raise OnlineStoreWriteError(
                format_actionable(
                    group=feature_group,
                    problem=(
                        f"existing DynamoDB table {table_name!r} has an unexpected key schema "
                        f"(expected exactly one HASH key, no RANGE key); "
                        f"partition key must be {entity_key_column!r}"
                    ),
                    next_step="drop or rename the table, or correct the feature group entity key",
                )
            )

        actual_name = hash_keys[0]["AttributeName"]
        actual_type = attr_defs.get(actual_name, "")

        if actual_name != entity_key_column:
            raise OnlineStoreWriteError(
                format_actionable(
                    group=feature_group,
                    problem=(
                        f"existing DynamoDB table partition key {actual_name!r} "
                        f"does not match the registered entity key {entity_key_column!r}"
                    ),
                    next_step="drop or rename the table, or correct the feature group entity key",
                )
            )

        if actual_type != key_attr_type:
            raise OnlineStoreWriteError(
                format_actionable(
                    group=feature_group,
                    problem=(
                        f"existing DynamoDB table partition key {entity_key_column!r} "
                        f"has type {actual_type!r} but the registered entity key requires {key_attr_type!r}"
                    ),
                    next_step="drop or rename the table, or correct the feature group entity key",
                )
            )

    def _batch_write(
        self,
        table_name: str,
        feature_group: str,
        items: list[dict[str, Any]],
    ) -> None:
        """Write *items* to *table_name* in BatchWriteItem chunks of at most 25.

        UnprocessedItems are retried exactly once after _UNPROCESSED_RETRY_DELAY_SECONDS.
        If items remain unprocessed after the retry, raises OnlineStoreWriteError.

        Raises ClientError / BotoCoreError — callers wrap those into domain errors.
        """
        # Split into chunks of at most 25 (DynamoDB BatchWriteItem limit).
        for start in range(0, len(items), 25):
            chunk = items[start : start + 25]
            request_items = {table_name: [{"PutRequest": {"Item": item}} for item in chunk]}

            resp = self._client.batch_write_item(RequestItems=request_items)
            unprocessed = resp.get("UnprocessedItems")

            if unprocessed:
                # Single retry after a short delay.
                time.sleep(_UNPROCESSED_RETRY_DELAY_SECONDS)
                retry_resp = self._client.batch_write_item(RequestItems=unprocessed)
                still_unprocessed = retry_resp.get("UnprocessedItems")

                if still_unprocessed:
                    count = sum(len(v) for v in still_unprocessed.values())
                    raise OnlineStoreWriteError(
                        format_actionable(
                            group=feature_group,
                            problem=(
                                f"{count} item(s) remained unprocessed after one retry "
                                f"for DynamoDB table {table_name!r}"
                            ),
                            next_step=("re-run materialize to retry; partial items may already be visible"),
                        )
                    )


__all__ = ["AWSOnlineStore"]
