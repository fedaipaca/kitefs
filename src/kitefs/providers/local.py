"""Local filesystem provider — reads and writes storage on the local filesystem."""

import os
import tempfile
from contextlib import suppress
from pathlib import Path

from pandas import DataFrame

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

    # --- Offline Store ---

    def write_offline(
        self,
        group_name: str,
        partition_path: str,
        file_name: str,
        df: DataFrame,
    ) -> None:
        """Write a single Parquet file to the specified partition path.

        Not yet implemented.
        """
        raise NotImplementedError("LocalProvider.write_offline is not yet implemented.")

    def read_offline(
        self,
        group_name: str,
        partition_paths: list[str],
    ) -> DataFrame:
        """Read and combine Parquet files from the specified partition paths.

        Not yet implemented.
        """
        raise NotImplementedError("LocalProvider.read_offline is not yet implemented.")

    def list_partitions(
        self,
        group_name: str,
    ) -> list[str]:
        """List available partition paths for a feature group.

        Not yet implemented.
        """
        raise NotImplementedError("LocalProvider.list_partitions is not yet implemented.")

    # --- Registry ---

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
