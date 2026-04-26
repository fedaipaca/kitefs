"""Local filesystem provider — reads and writes storage on the local filesystem."""

import os
import re
import tempfile
from contextlib import suppress
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pandas import DataFrame

from kitefs.config import Config
from kitefs.exceptions import ProviderError
from kitefs.providers.base import StorageProvider

_YEAR_PATTERN = re.compile(r"year=\d{4}")
_MONTH_PATTERN = re.compile(r"month=\d{2}")


class LocalProvider(StorageProvider):
    """Storage provider backed by the local filesystem.

    Registry: reads/writes registry.json at {storage_root}/registry.json.
    Offline store: Parquet files under {storage_root}/data/offline_store/.
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
        """Write a DataFrame as a Parquet file to the local offline store.

        Creates the full directory structure under
        ``{storage_root}/data/offline_store/{group_name}/{partition_path}/``
        and writes the file atomically via a temporary file and ``os.replace``.
        """
        target_dir = self._storage_root / "data" / "offline_store" / group_name / Path(partition_path)
        target_path = target_dir / file_name
        temp_file_path: str | None = None

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            file_descriptor, temp_file_path = tempfile.mkstemp(
                dir=target_dir,
                prefix=f"{file_name}.",
                suffix=".tmp",
            )
            os.close(file_descriptor)

            table = pa.Table.from_pandas(df)
            pq.write_table(table, temp_file_path)

            os.replace(temp_file_path, target_path)
        except (OSError, pa.lib.ArrowException) as exc:
            if temp_file_path is not None:
                with suppress(OSError):
                    os.unlink(temp_file_path)
            raise ProviderError(
                f"Failed to write offline Parquet file to '{target_path}': {exc}. "
                "Check file permissions and available disk space."
            ) from exc

    def read_offline(
        self,
        group_name: str,
        partition_paths: list[str],
    ) -> DataFrame:
        """Read and combine Parquet files from the specified local partition paths.

        For each partition path, reads all ``.parquet`` files under
        ``{storage_root}/data/offline_store/{group_name}/{partition_path}/``.
        Non-existent partition directories are skipped gracefully.
        Returns an empty DataFrame when no files are found across all partitions.
        """
        group_base = self._storage_root / "data" / "offline_store" / group_name
        tables: list[pa.Table] = []

        try:
            for partition_path in partition_paths:
                partition_dir = group_base / Path(partition_path)
                if not partition_dir.is_dir():
                    continue
                for parquet_file in sorted(partition_dir.glob("*.parquet")):
                    tables.append(pq.read_table(parquet_file))

            if not tables:
                return DataFrame()

            return pa.concat_tables(tables).to_pandas()
        except (OSError, pa.lib.ArrowException) as exc:
            raise ProviderError(
                f"Failed to read offline Parquet files for '{group_name}': {exc}. "
                "Check file permissions and that the Parquet files are not corrupted."
            ) from exc

    def list_partitions(
        self,
        group_name: str,
    ) -> list[str]:
        """List available Hive-style partition paths for a feature group.

        Enumerates ``year=YYYY/month=MM`` subdirectories under the group's
        offline store directory. Returns a sorted list of relative partition
        paths, or an empty list if the group directory does not exist.
        """
        group_base = self._storage_root / "data" / "offline_store" / group_name
        if not group_base.is_dir():
            return []

        partitions: list[str] = []
        try:
            for year_dir in sorted(group_base.iterdir()):
                if not year_dir.is_dir() or not _YEAR_PATTERN.fullmatch(year_dir.name):
                    continue
                for month_dir in sorted(year_dir.iterdir()):
                    if not month_dir.is_dir() or not _MONTH_PATTERN.fullmatch(month_dir.name):
                        continue
                    partitions.append(f"{year_dir.name}/{month_dir.name}")
        except OSError as exc:
            raise ProviderError(
                f"Failed to list partitions for '{group_name}': {exc}. "
                "Check that the offline store directory is readable."
            ) from exc

        return partitions

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
