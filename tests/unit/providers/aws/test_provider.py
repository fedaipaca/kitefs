"""Unit tests for kitefs.providers.aws AWSProvider configuration and construction."""

from __future__ import annotations

import sys
from typing import Any

import pytest

from kitefs.errors import ConfigurationError, ProviderError
from kitefs.providers.aws import AWSProvider
from kitefs.providers.base import OfflineStore, OnlineStore, Provider, RegistryStore

_VALID_REMOTE: dict[str, Any] = {
    "region": "eu-central-1",
    "registry": {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"},
    "offline_store": {"type": "aws_s3", "bucket": "test-bucket", "s3_prefix": "kitefs"},
    "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": "kitefs_"},
}


@pytest.fixture(autouse=True)
def _use_mocked_aws(mocked_aws: None) -> None:
    """Use moto-backed AWS clients for all tests in this module."""


class TestAWSProviderConstruction:
    """AWSProvider constructs and exposes the correct store instances."""

    def test_is_provider_subclass(self) -> None:
        """AWSProvider satisfies the Provider ABC."""
        assert isinstance(AWSProvider(_VALID_REMOTE), Provider)

    def test_registry_store_returns_registry_store(self) -> None:
        """registry_store() returns a RegistryStore instance."""
        assert isinstance(AWSProvider(_VALID_REMOTE).registry_store(), RegistryStore)

    def test_offline_store_returns_offline_store(self) -> None:
        """offline_store() returns an OfflineStore instance."""
        assert isinstance(AWSProvider(_VALID_REMOTE).offline_store(), OfflineStore)

    def test_online_store_returns_online_store(self) -> None:
        """online_store() returns an OnlineStore instance."""
        assert isinstance(AWSProvider(_VALID_REMOTE).online_store(), OnlineStore)


class TestAWSProviderMissingRegion:
    """AWSProvider raises ConfigurationError when region is missing or empty."""

    def test_missing_region_raises(self) -> None:
        """ConfigurationError when remote.region is absent."""
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider({**_VALID_REMOTE, "region": ""})
        assert "remote.region" in str(exc_info.value)

    def test_absent_region_key_raises(self) -> None:
        """ConfigurationError when remote.region key is not present."""
        remote = {k: v for k, v in _VALID_REMOTE.items() if k != "region"}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote)
        assert "remote.region" in str(exc_info.value)


class TestAWSProviderRegistryValidation:
    """registry_store() raises ConfigurationError for invalid registry config."""

    def test_absent_registry_section_raises(self) -> None:
        """ConfigurationError when remote.registry is absent."""
        remote = {k: v for k, v in _VALID_REMOTE.items() if k != "registry"}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).registry_store()
        assert "remote.registry" in str(exc_info.value)

    def test_empty_registry_bucket_raises(self) -> None:
        """ConfigurationError when remote.registry.bucket is empty."""
        remote = {**_VALID_REMOTE, "registry": {"type": "aws_s3", "bucket": "", "s3_prefix": "kitefs"}}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).registry_store()
        assert "remote.registry.bucket" in str(exc_info.value)

    def test_empty_registry_prefix_raises(self) -> None:
        """ConfigurationError when remote.registry.s3_prefix is empty."""
        remote = {**_VALID_REMOTE, "registry": {"type": "aws_s3", "bucket": "b", "s3_prefix": ""}}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).registry_store()
        assert "remote.registry.s3_prefix" in str(exc_info.value)

    @pytest.mark.parametrize(
        "registry_section",
        [
            pytest.param({"bucket": "b", "s3_prefix": "p"}, id="missing_type"),
            pytest.param({"type": "gcs_bucket", "bucket": "b", "s3_prefix": "p"}, id="wrong_type"),
        ],
    )
    def test_invalid_registry_type_raises(self, registry_section: dict[str, Any]) -> None:
        """ConfigurationError naming remote.registry.type when type is missing or wrong."""
        remote = {**_VALID_REMOTE, "registry": registry_section}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).registry_store()
        msg = str(exc_info.value)
        assert "remote.registry.type" in msg
        assert "aws_s3" in msg


class TestAWSProviderOfflineValidation:
    """offline_store() raises ConfigurationError for invalid offline config."""

    def test_absent_offline_section_raises(self) -> None:
        """ConfigurationError containing 'remote offline' when offline_store is absent."""
        remote = {k: v for k, v in _VALID_REMOTE.items() if k != "offline_store"}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).offline_store()
        assert "remote offline" in str(exc_info.value)

    def test_empty_offline_bucket_raises(self) -> None:
        """ConfigurationError when remote.offline_store.bucket is empty."""
        remote = {**_VALID_REMOTE, "offline_store": {"type": "aws_s3", "bucket": "", "s3_prefix": "kitefs"}}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).offline_store()
        assert "remote.offline_store.bucket" in str(exc_info.value)

    @pytest.mark.parametrize(
        "offline_section",
        [
            pytest.param({"bucket": "b", "s3_prefix": "p"}, id="missing_type"),
            pytest.param({"type": "gcs_bucket", "bucket": "b", "s3_prefix": "p"}, id="wrong_type"),
        ],
    )
    def test_invalid_offline_type_raises(self, offline_section: dict[str, Any]) -> None:
        """ConfigurationError naming remote.offline_store.type when type is missing or wrong."""
        remote = {**_VALID_REMOTE, "offline_store": offline_section}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).offline_store()
        msg = str(exc_info.value)
        assert "remote.offline_store.type" in msg
        assert "aws_s3" in msg


class TestAWSProviderOnlineValidation:
    """online_store() raises ConfigurationError for invalid online config."""

    def test_absent_online_section_raises(self) -> None:
        """ConfigurationError when remote.online_store is absent."""
        remote = {k: v for k, v in _VALID_REMOTE.items() if k != "online_store"}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).online_store()
        assert "remote.online_store" in str(exc_info.value)

    def test_empty_table_prefix_raises(self) -> None:
        """ConfigurationError when remote.online_store.dynamodb_table_prefix is empty."""
        remote = {**_VALID_REMOTE, "online_store": {"type": "aws_dynamodb", "dynamodb_table_prefix": ""}}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).online_store()
        assert "remote.online_store.dynamodb_table_prefix" in str(exc_info.value)

    @pytest.mark.parametrize(
        "online_section",
        [
            pytest.param({"dynamodb_table_prefix": "p_"}, id="missing_type"),
            pytest.param({"type": "redis", "dynamodb_table_prefix": "p_"}, id="wrong_type"),
        ],
    )
    def test_invalid_online_type_raises(self, online_section: dict[str, Any]) -> None:
        """ConfigurationError naming remote.online_store.type when type is missing or wrong."""
        remote = {**_VALID_REMOTE, "online_store": online_section}
        with pytest.raises(ConfigurationError) as exc_info:
            AWSProvider(remote).online_store()
        msg = str(exc_info.value)
        assert "remote.online_store.type" in msg
        assert "aws_dynamodb" in msg


class TestAWSProviderBoto3Missing:
    """AWSProvider raises ProviderError when boto3 is not installed."""

    def test_boto3_missing_raises_provider_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ProviderError message contains 'boto3' and 'kitefs[aws]'."""
        monkeypatch.setitem(sys.modules, "boto3", None)
        with pytest.raises(ProviderError) as exc_info:
            AWSProvider(_VALID_REMOTE)
        msg = str(exc_info.value)
        assert "boto3" in msg
        assert "kitefs[aws]" in msg
