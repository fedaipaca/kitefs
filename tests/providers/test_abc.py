"""Tests for the StorageProvider ABC contract."""

import pytest

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

    def test_partial_subclass_missing_write_raises_type_error(self) -> None:
        """A subclass missing write_registry raises TypeError."""

        class ReadOnlyProvider(StorageProvider):
            def read_registry(self) -> str:
                return ""

            # write_registry not implemented

        with pytest.raises(TypeError):
            ReadOnlyProvider()  # type: ignore[abstract]

    def test_partial_subclass_missing_read_raises_type_error(self) -> None:
        """A subclass missing read_registry raises TypeError."""

        class WriteOnlyProvider(StorageProvider):
            def write_registry(self, data: str) -> None:
                pass

            # read_registry not implemented

        with pytest.raises(TypeError):
            WriteOnlyProvider()  # type: ignore[abstract]

    def test_complete_subclass_can_be_instantiated(self) -> None:
        """A subclass implementing both methods can be instantiated."""

        class FullProvider(StorageProvider):
            def read_registry(self) -> str:
                return ""

            def write_registry(self, data: str) -> None:
                pass

        provider = FullProvider()
        assert isinstance(provider, StorageProvider)
