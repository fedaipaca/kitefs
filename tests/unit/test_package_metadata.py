import kitefs


class TestPackageMetadata:
    """Asserts package-level metadata is correct and importable."""

    def test_version_is_string(self) -> None:
        """__version__ is a string."""
        assert isinstance(kitefs.__version__, str)

    def test_version_value(self) -> None:
        """__version__ matches the declared package version."""
        assert kitefs.__version__ == "0.1.0"

    def test_import_does_not_raise(self) -> None:
        """Importing kitefs raises no exception."""
        import importlib

        importlib.import_module("kitefs")
