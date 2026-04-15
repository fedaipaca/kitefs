"""Provider abstraction layer — abstract base class for all storage backends."""

from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Abstract base class for all KiteFS storage backends.

    Defines the storage interface that all providers must implement.
    Core modules (SDK, registry, validation, join engine) interact with
    storage exclusively through this interface.

    Uses ABC with @abstractmethod, not Protocol: gives an immediate
    TypeError at instantiation if any method is missing, which is preferable
    for a small, known set of providers where correctness is critical.

    The interface grows incrementally; currently only registry methods are defined.
    Offline store and online store methods will be added in later phases.
    """

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
