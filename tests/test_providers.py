"""Tests for the provider layer — StorageProvider ABC, LocalProvider, and factory."""

import os
from pathlib import Path

import pytest
from helpers import make_local_config

from kitefs.config import AWSConfig, Config
from kitefs.exceptions import ProviderError
from kitefs.providers import LocalProvider, StorageProvider, create_provider


def _make_aws_config(tmp_path: Path) -> Config:
    """Build a minimal AWS Config for factory error tests."""
    storage_root = tmp_path / "feature_store"
    return Config(
        provider="aws",
        project_root=tmp_path,
        storage_root=storage_root,
        definitions_path=storage_root / "definitions",
        aws=AWSConfig(
            s3_bucket="my-bucket",
            s3_prefix="kitefs/",
            dynamodb_table_prefix="kitefs_",
        ),
    )


class TestStorageProviderABC:
    """The ABC cannot be instantiated and enforces complete implementation."""

    def test_cannot_instantiate_abc_directly(self) -> None:
        with pytest.raises(TypeError):
            StorageProvider()  # type: ignore[abstract]

    def test_empty_subclass_raises_type_error(self) -> None:
        class EmptyProvider(StorageProvider):
            pass

        with pytest.raises(TypeError):
            EmptyProvider()  # type: ignore[abstract]

    def test_partial_subclass_missing_write_raises_type_error(self) -> None:
        class ReadOnlyProvider(StorageProvider):
            def read_registry(self) -> str:
                return ""

            # write_registry not implemented

        with pytest.raises(TypeError):
            ReadOnlyProvider()  # type: ignore[abstract]

    def test_partial_subclass_missing_read_raises_type_error(self) -> None:
        class WriteOnlyProvider(StorageProvider):
            def write_registry(self, data: str) -> None:
                pass

            # read_registry not implemented

        with pytest.raises(TypeError):
            WriteOnlyProvider()  # type: ignore[abstract]

    def test_complete_subclass_can_be_instantiated(self) -> None:
        class FullProvider(StorageProvider):
            def read_registry(self) -> str:
                return ""

            def write_registry(self, data: str) -> None:
                pass

        provider = FullProvider()
        assert isinstance(provider, StorageProvider)


class TestLocalProviderReadRegistry:
    """LocalProvider.read_registry — success and error paths."""

    def test_read_existing_registry_returns_content(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        config.storage_root.mkdir(parents=True)
        (config.storage_root / "registry.json").write_text('{"version": "1.0"}', encoding="utf-8")

        provider = LocalProvider(config)
        result = provider.read_registry()

        assert result == '{"version": "1.0"}'

    def test_read_missing_registry_raises_provider_error(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)

        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match="Registry not found"):
            provider.read_registry()

    def test_missing_registry_error_mentions_kitefs_init(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match="kitefs init"):
            provider.read_registry()

    def test_missing_registry_error_mentions_path(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match=r"registry\.json"):
            provider.read_registry()

    def test_read_unreadable_file_raises_provider_error(self, tmp_path: Path) -> None:
        if os.name == "nt":
            pytest.skip("File permission test is not reliable on Windows.")

        config = make_local_config(tmp_path)
        config.storage_root.mkdir(parents=True)
        registry = config.storage_root / "registry.json"
        registry.write_text('{"version": "1.0"}', encoding="utf-8")
        os.chmod(registry, 0o000)

        try:
            if os.access(registry, os.R_OK):
                pytest.skip("Could not make file non-readable in this environment.")

            provider = LocalProvider(config)
            with pytest.raises(ProviderError, match="Failed to read registry"):
                provider.read_registry()
        finally:
            os.chmod(registry, 0o644)


class TestLocalProviderWriteRegistry:
    """LocalProvider.write_registry — file creation, content, and directory creation."""

    def test_write_creates_registry_file(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')

        assert (config.storage_root / "registry.json").exists()

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        assert not config.storage_root.exists()

        provider = LocalProvider(config)
        provider.write_registry('{"version": "1.0"}')

        assert config.storage_root.is_dir()

    def test_write_stores_exact_content(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        data = '{\n  "version": "1.0",\n  "feature_groups": {}\n}'

        provider = LocalProvider(config)
        provider.write_registry(data)

        on_disk = (config.storage_root / "registry.json").read_text(encoding="utf-8")
        assert on_disk == data

    def test_write_overwrites_existing_content(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')
        provider.write_registry('{"version": "2.0"}')

        on_disk = (config.storage_root / "registry.json").read_text(encoding="utf-8")
        assert on_disk == '{"version": "2.0"}'

    def test_write_registry_unwritable_directory_raises_provider_error(self, tmp_path: Path) -> None:
        if os.name == "nt":
            pytest.skip("Permission-based directory write test is not reliable on Windows.")

        read_only_parent = tmp_path / "read_only_parent"
        read_only_parent.mkdir()
        original_mode = read_only_parent.stat().st_mode & 0o777
        os.chmod(read_only_parent, 0o555)

        try:
            if os.access(read_only_parent, os.W_OK):
                pytest.skip("Could not make directory non-writable in this environment.")

            storage_root = read_only_parent / "feature_store"
            config = Config(
                provider="local",
                project_root=tmp_path,
                storage_root=storage_root,
                definitions_path=storage_root / "definitions",
                aws=None,
            )
            provider = LocalProvider(config)

            with pytest.raises(ProviderError, match="Failed to write registry"):
                provider.write_registry('{"version": "1.0"}')
        finally:
            os.chmod(read_only_parent, original_mode)


class TestLocalProviderRegistryRoundtrip:
    """Read/write roundtrip — the provider does raw string I/O, no JSON interpretation."""

    def test_roundtrip_returns_exact_string(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        original = '{\n  "version": "1.0",\n  "feature_groups": {}\n}'

        provider.write_registry(original)
        result = provider.read_registry()

        assert result == original

    def test_roundtrip_preserves_unicode(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        data = '{"name": "café_features", "emoji": "🪁"}'

        provider.write_registry(data)

        assert provider.read_registry() == data

    def test_roundtrip_preserves_whitespace_and_formatting(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        # Simulate deterministic JSON output as produced by the registry manager
        data = '{\n  "feature_groups": {},\n  "version": "1.0"\n}'

        provider.write_registry(data)

        assert provider.read_registry() == data

    def test_write_and_read_empty_string(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry("")

        assert provider.read_registry() == ""

    def test_multiple_writes_last_write_wins(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')
        provider.write_registry('{"version": "1.1"}')
        provider.write_registry('{"version": "1.2"}')

        assert provider.read_registry() == '{"version": "1.2"}'


class TestCreateProvider:
    """Provider factory — correct dispatch and error cases."""

    def test_local_config_returns_local_provider(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)

        provider = create_provider(config)

        assert isinstance(provider, LocalProvider)

    def test_local_provider_is_storage_provider_instance(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)

        provider = create_provider(config)

        assert isinstance(provider, StorageProvider)

    def test_aws_config_raises_provider_error(self, tmp_path: Path) -> None:
        config = _make_aws_config(tmp_path)

        with pytest.raises(ProviderError, match="AWS provider is not yet implemented"):
            create_provider(config)

    def test_aws_error_suggests_local_alternative(self, tmp_path: Path) -> None:
        config = _make_aws_config(tmp_path)

        with pytest.raises(ProviderError, match="provider: local"):
            create_provider(config)

    def test_unknown_provider_raises_provider_error(self, tmp_path: Path) -> None:
        storage_root = tmp_path / "feature_store"
        config = Config(
            provider="gcp",
            project_root=tmp_path,
            storage_root=storage_root,
            definitions_path=storage_root / "definitions",
            aws=None,
        )

        with pytest.raises(ProviderError, match=r"Unknown provider 'gcp'.*Supported providers: local"):
            create_provider(config)

    def test_returned_local_provider_can_write_and_read(self, tmp_path: Path) -> None:
        """Integration smoke test: factory-created provider works end-to-end."""
        config = make_local_config(tmp_path)
        provider = create_provider(config)
        data = '{"version": "1.0", "feature_groups": {}}'

        provider.write_registry(data)

        assert provider.read_registry() == data

    def test_factory_returns_distinct_instances(self, tmp_path: Path) -> None:
        config = make_local_config(tmp_path)

        p1 = create_provider(config)
        p2 = create_provider(config)

        assert p1 is not p2
