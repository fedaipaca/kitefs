import importlib
import importlib.metadata

import kitefs


class TestPackageMetadata:
    """Asserts package-level metadata is correct and importable."""

    def test_version_is_string(self) -> None:
        """__version__ is a string."""
        assert isinstance(kitefs.__version__, str)

    def test_version_matches_package_metadata(self) -> None:
        """__version__ matches the version declared in package metadata."""
        assert kitefs.__version__ == importlib.metadata.version("kitefs")

    def test_import_does_not_raise(self) -> None:
        """Importing kitefs raises no exception."""
        importlib.import_module("kitefs")
