"""Provider abstraction layer — abstract base class for all storage backends."""

from abc import ABC, abstractmethod

from pandas import DataFrame


class StorageProvider(ABC):
    """Abstract base class for all KiteFS storage backends.

    Defines the storage interface that all providers must implement.
    Core modules (SDK, registry, validation, join engine) interact with
    storage exclusively through this interface.

    Uses ABC with @abstractmethod, not Protocol: gives an immediate
    TypeError at instantiation if any method is missing, which is preferable
    for a small, known set of providers where correctness is critical.
    """

    # --- Offline Store ---

    @abstractmethod
    def write_offline(
        self,
        group_name: str,
        partition_path: str,
        file_name: str,
        df: DataFrame,
    ) -> None:
        """Write a single Parquet file to the specified partition path.

        Stores the file at {storage_root}/data/offline_store/{group_name}/{partition_path}/{file_name}.
        Partition derivation and file naming are the caller's responsibility.
        Raises ProviderError on I/O failure.
        """

    @abstractmethod
    def read_offline(
        self,
        group_name: str,
        partition_paths: list[str],
    ) -> DataFrame:
        """Read and combine Parquet files from the specified partition paths.

        Returns a single DataFrame combining all files found in the given partitions.
        Returns an empty DataFrame if no files exist; skips non-existent paths gracefully.
        Raises ProviderError on I/O failure.
        """

    @abstractmethod
    def list_partitions(
        self,
        group_name: str,
    ) -> list[str]:
        """List available partition paths for a feature group.

        Returns a sorted list of relative partition paths (e.g., ["year=2024/month=01"]).
        Returns an empty list if the group has no partitions or does not exist.
        """

    # --- Registry ---

    @abstractmethod
    def read_registry(self) -> str:
        """Read the registry JSON string from storage.

        Returns the raw JSON string. JSON parsing is the caller's responsibility.
        Raises ProviderError if the registry cannot be read (missing or I/O failure).
        """

    @abstractmethod
    def write_registry(self, data: str) -> None:
        """Write the registry JSON string to storage.

        Accepts the raw JSON string. JSON serialization is the caller's responsibility.
        Creates any necessary parent directories on first write.
        Raises ProviderError if the registry cannot be written.
        """
