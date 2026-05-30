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


def create_dynamodb_table(client: Any, *, table_name: str, hash_key: str) -> None:
    """Create a simple string-keyed DynamoDB table in moto."""
    client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": hash_key, "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": hash_key, "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
