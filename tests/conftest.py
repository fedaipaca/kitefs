"""Root-level shared pytest fixtures for KiteFS tests.

Fixtures here are available to all test tiers (unit, integration, bdd).
Scope them appropriately — prefer function-scoped unless reuse is expensive.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Generator

import pytest


@pytest.fixture
def fake_boto3(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Install a minimal fake boto3 in sys.modules.

    Allows AWS provider tests to construct AWSProvider instances without the
    optional kitefs[aws] extra or real AWS credentials.  The patch is reverted
    automatically after each test by monkeypatch teardown.
    """

    class _FakeClient:
        pass

    fake = types.SimpleNamespace(
        client=lambda service_name, region_name=None: _FakeClient(),
    )
    monkeypatch.setitem(sys.modules, "boto3", fake)
    yield
