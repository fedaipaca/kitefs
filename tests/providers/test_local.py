"""Tests for LocalProvider — read, write, and roundtrip."""

import os
from pathlib import Path

import pytest
from helpers import make_local_config

from kitefs.config import Config
from kitefs.exceptions import ProviderError
from kitefs.providers import LocalProvider


class TestLocalProviderReadRegistry:
    """LocalProvider.read_registry — success and error paths."""

    def test_read_existing_registry_returns_content(self, tmp_path: Path) -> None:
        """Reading an existing registry.json returns its content."""
        config = make_local_config(tmp_path)
        config.storage_root.mkdir(parents=True)
        (config.storage_root / "registry.json").write_text('{"version": "1.0"}', encoding="utf-8")

        provider = LocalProvider(config)
        result = provider.read_registry()

        assert result == '{"version": "1.0"}'

    def test_read_missing_registry_raises_provider_error(self, tmp_path: Path) -> None:
        """Reading a non-existent registry.json raises ProviderError."""
        config = make_local_config(tmp_path)

        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match="Registry not found"):
            provider.read_registry()

    def test_missing_registry_error_mentions_kitefs_init(self, tmp_path: Path) -> None:
        """Missing registry error suggests running kitefs init."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match="kitefs init"):
            provider.read_registry()

    def test_missing_registry_error_mentions_path(self, tmp_path: Path) -> None:
        """Missing registry error includes the expected file path."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(ProviderError, match=r"registry\.json"):
            provider.read_registry()

    def test_read_unreadable_file_raises_provider_error(self, tmp_path: Path) -> None:
        """A non-readable registry.json raises ProviderError."""
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
        """write_registry creates the registry.json file."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')

        assert (config.storage_root / "registry.json").exists()

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """write_registry creates missing parent directories."""
        config = make_local_config(tmp_path)
        assert not config.storage_root.exists()

        provider = LocalProvider(config)
        provider.write_registry('{"version": "1.0"}')

        assert config.storage_root.is_dir()

    def test_write_stores_exact_content(self, tmp_path: Path) -> None:
        """write_registry stores the exact string content provided."""
        config = make_local_config(tmp_path)
        data = '{\n  "version": "1.0",\n  "feature_groups": {}\n}'

        provider = LocalProvider(config)
        provider.write_registry(data)

        on_disk = (config.storage_root / "registry.json").read_text(encoding="utf-8")
        assert on_disk == data

    def test_write_overwrites_existing_content(self, tmp_path: Path) -> None:
        """write_registry overwrites the previous content."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')
        provider.write_registry('{"version": "2.0"}')

        on_disk = (config.storage_root / "registry.json").read_text(encoding="utf-8")
        assert on_disk == '{"version": "2.0"}'

    def test_write_registry_unwritable_directory_raises_provider_error(self, tmp_path: Path) -> None:
        """Writing to a non-writable directory raises ProviderError."""
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
        """Write then read returns the exact same string."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        original = '{\n  "version": "1.0",\n  "feature_groups": {}\n}'

        provider.write_registry(original)
        result = provider.read_registry()

        assert result == original

    def test_roundtrip_preserves_unicode(self, tmp_path: Path) -> None:
        """Roundtrip preserves Unicode characters."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        data = '{"name": "café_features", "emoji": "🪁"}'

        provider.write_registry(data)

        assert provider.read_registry() == data

    def test_roundtrip_preserves_whitespace_and_formatting(self, tmp_path: Path) -> None:
        """Roundtrip preserves exact whitespace and JSON formatting."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)
        # Simulate deterministic JSON output as produced by the registry manager
        data = '{\n  "feature_groups": {},\n  "version": "1.0"\n}'

        provider.write_registry(data)

        assert provider.read_registry() == data

    def test_write_and_read_empty_string(self, tmp_path: Path) -> None:
        """Roundtrip of an empty string works."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry("")

        assert provider.read_registry() == ""

    def test_multiple_writes_last_write_wins(self, tmp_path: Path) -> None:
        """Multiple writes keep only the last written content."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        provider.write_registry('{"version": "1.0"}')
        provider.write_registry('{"version": "1.1"}')
        provider.write_registry('{"version": "1.2"}')

        assert provider.read_registry() == '{"version": "1.2"}'


class TestLocalProviderOfflineStubs:
    """LocalProvider offline methods raise NotImplementedError until implemented."""

    def test_write_offline_raises_not_implemented(self, tmp_path: Path) -> None:
        """write_offline is stubbed and raises NotImplementedError."""
        from pandas import DataFrame

        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(NotImplementedError):
            provider.write_offline("group", "year=2024/month=01", "file.parquet", DataFrame())

    def test_read_offline_raises_not_implemented(self, tmp_path: Path) -> None:
        """read_offline is stubbed and raises NotImplementedError."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(NotImplementedError):
            provider.read_offline("group", ["year=2024/month=01"])

    def test_list_partitions_raises_not_implemented(self, tmp_path: Path) -> None:
        """list_partitions is stubbed and raises NotImplementedError."""
        config = make_local_config(tmp_path)
        provider = LocalProvider(config)

        with pytest.raises(NotImplementedError):
            provider.list_partitions("group")
