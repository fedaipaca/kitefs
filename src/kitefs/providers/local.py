"""Local filesystem provider — reads and writes storage on the local filesystem."""

import os
import tempfile
from contextlib import suppress
from pathlib import Path

from kitefs.config import Config
from kitefs.exceptions import ProviderError
from kitefs.providers.base import StorageProvider


class LocalProvider(StorageProvider):
    """Storage provider backed by the local filesystem.

    Registry: reads/writes registry.json at {storage_root}/registry.json.
    Offline store: Parquet files under {storage_root}/data/offline_store/ (not yet implemented).
    Online store: SQLite at {storage_root}/data/online_store/online.db (not yet implemented).
    """

    def __init__(self, config: Config) -> None:
        """Initialise with a validated config."""
        self._storage_root: Path = config.storage_root
        self._registry_path: Path = self._storage_root / "registry.json"

    def read_registry(self) -> str:
        """Read registry.json as a UTF-8 string from the configured storage root.

        Raises ProviderError if the file does not exist or cannot be read.
        """
        if not self._registry_path.exists():
            raise ProviderError(
                f"Registry not found at '{self._registry_path}'. "
                "Run `kitefs init` to create a project, then `kitefs apply` to register definitions."
            )
        try:
            return self._registry_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProviderError(
                f"Failed to read registry at '{self._registry_path}': {exc}. "
                "Check that the file is readable and that you have sufficient permissions."
            ) from exc

    def write_registry(self, data: str) -> None:
        """Write a UTF-8 string to registry.json, creating parent directories if needed.

        Raises ProviderError if the file cannot be written.
        """
        temp_file_path: str | None = None
        try:
            self._registry_path.parent.mkdir(parents=True, exist_ok=True)
            file_descriptor, temp_file_path = tempfile.mkstemp(
                dir=self._registry_path.parent,
                prefix=f"{self._registry_path.name}.",
                suffix=".tmp",
            )

            with os.fdopen(file_descriptor, "w", encoding="utf-8") as temp_file:
                temp_file.write(data)

            os.replace(temp_file_path, self._registry_path)
        except OSError as exc:
            if temp_file_path is not None:
                with suppress(OSError):
                    os.unlink(temp_file_path)
            raise ProviderError(
                f"Failed to write registry to '{self._registry_path}': {exc}. "
                "Check file permissions and available disk space."
            ) from exc
