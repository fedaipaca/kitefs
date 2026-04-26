"""Tests for the StorageProvider ABC contract."""

import pytest
from pandas import DataFrame

from kitefs.providers import StorageProvider


class TestStorageProviderABC:
    """The ABC cannot be instantiated and enforces complete implementation."""

    def test_cannot_instantiate_abc_directly(self) -> None:
        """StorageProvider ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            StorageProvider()  # type: ignore[abstract]

    def test_empty_subclass_raises_type_error(self) -> None:
        """A subclass with no methods raises TypeError on instantiation."""

        class EmptyProvider(StorageProvider):
            pass

        with pytest.raises(TypeError):
            EmptyProvider()  # type: ignore[abstract]

    def test_partial_subclass_missing_write_registry_raises_type_error(self) -> None:
        """A subclass missing write_registry raises TypeError."""

        class ReadOnlyProvider(StorageProvider):
            def read_registry(self) -> str:
                return ""

            # write_registry not implemented

        with pytest.raises(TypeError):
            ReadOnlyProvider()  # type: ignore[abstract]

    def test_partial_subclass_missing_read_registry_raises_type_error(self) -> None:
        """A subclass missing read_registry raises TypeError."""

        class WriteOnlyProvider(StorageProvider):
            def write_registry(self, data: str) -> None:
                pass

            # read_registry not implemented

        with pytest.raises(TypeError):
            WriteOnlyProvider()  # type: ignore[abstract]

    def test_subclass_with_only_registry_methods_raises_type_error(self) -> None:
        """A subclass implementing only the registry methods raises TypeError — offline methods are now required."""

        class RegistryOnlyProvider(StorageProvider):
            def read_registry(self) -> str:
                return ""

            def write_registry(self, data: str) -> None:
                pass

        with pytest.raises(TypeError):
            RegistryOnlyProvider()  # type: ignore[abstract]

    def test_subclass_missing_write_offline_raises_type_error(self) -> None:
        """A subclass missing write_offline raises TypeError on instantiation."""

        class MissingWriteOffline(StorageProvider):
            def read_registry(self) -> str:
                return ""

            def write_registry(self, data: str) -> None:
                pass

            def read_offline(self, group_name: str, partition_paths: list[str]) -> DataFrame:
                return DataFrame()

            def list_partitions(self, group_name: str) -> list[str]:
                return []

            # write_offline not implemented

        with pytest.raises(TypeError):
            MissingWriteOffline()  # type: ignore[abstract]

    def test_subclass_missing_read_offline_raises_type_error(self) -> None:
        """A subclass missing read_offline raises TypeError on instantiation."""

        class MissingReadOffline(StorageProvider):
            def read_registry(self) -> str:
                return ""

            def write_registry(self, data: str) -> None:
                pass

            def write_offline(self, group_name: str, partition_path: str, file_name: str, df: DataFrame) -> None:
                pass

            def list_partitions(self, group_name: str) -> list[str]:
                return []

            # read_offline not implemented

        with pytest.raises(TypeError):
            MissingReadOffline()  # type: ignore[abstract]

    def test_subclass_missing_list_partitions_raises_type_error(self) -> None:
        """A subclass missing list_partitions raises TypeError on instantiation."""

        class MissingListPartitions(StorageProvider):
            def read_registry(self) -> str:
                return ""

            def write_registry(self, data: str) -> None:
                pass

            def write_offline(self, group_name: str, partition_path: str, file_name: str, df: DataFrame) -> None:
                pass

            def read_offline(self, group_name: str, partition_paths: list[str]) -> DataFrame:
                return DataFrame()

            # list_partitions not implemented

        with pytest.raises(TypeError):
            MissingListPartitions()  # type: ignore[abstract]

    def test_complete_subclass_with_all_methods_can_be_instantiated(self) -> None:
        """A subclass implementing all five methods (registry + offline) can be instantiated."""

        class FullProvider(StorageProvider):
            def read_registry(self) -> str:
                return ""

            def write_registry(self, data: str) -> None:
                pass

            def write_offline(self, group_name: str, partition_path: str, file_name: str, df: DataFrame) -> None:
                pass

            def read_offline(self, group_name: str, partition_paths: list[str]) -> DataFrame:
                return DataFrame()

            def list_partitions(self, group_name: str) -> list[str]:
                return []

        provider = FullProvider()
        assert isinstance(provider, StorageProvider)
