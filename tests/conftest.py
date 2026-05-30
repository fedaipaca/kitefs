"""Root-level shared pytest fixtures for KiteFS tests.

Fixtures here are available to all test tiers (unit, integration, bdd).
Scope them appropriately — prefer function-scoped unless reuse is expensive.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from moto import mock_aws


@pytest.fixture
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy AWS credentials for moto-backed tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


@pytest.fixture
def mocked_aws(aws_credentials: None) -> Generator[None, None, None]:
    """Run a test inside moto's in-memory AWS backend."""
    with mock_aws():
        yield
