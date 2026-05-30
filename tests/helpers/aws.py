"""Shared moto-backed AWS resource helpers for tests."""

from __future__ import annotations

from typing import Any


def create_s3_bucket(client: Any, *, bucket: str, region: str) -> None:
    """Create an S3 bucket in moto for the requested region."""
    if region == "us-east-1":
        client.create_bucket(Bucket=bucket)
        return

    client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": region},
    )


def create_dynamodb_table(client: Any, *, table_name: str, hash_key: str, key_type: str = "S") -> None:
    """Create a DynamoDB table with a single HASH key in moto.

    Args:
        client: boto3 DynamoDB client.
        table_name: Name of the table to create.
        hash_key: Attribute name for the partition key.
        key_type: DynamoDB attribute type for the partition key — "S" (string,
            default) or "N" (number).
    """
    client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": hash_key, "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": hash_key, "AttributeType": key_type}],
        BillingMode="PAY_PER_REQUEST",
    )
