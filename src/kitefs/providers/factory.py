"""Provider factory — instantiates the correct provider from config."""

from kitefs.config import Config
from kitefs.exceptions import ProviderError
from kitefs.providers.base import StorageProvider
from kitefs.providers.local import LocalProvider


def create_provider(config: Config) -> StorageProvider:
    """Instantiate the storage provider specified in config.

    Returns a LocalProvider for provider='local'.
    Raises ProviderError for provider='aws' (not yet implemented) or any unknown value.
    """
    if config.provider == "local":
        return LocalProvider(config)
    if config.provider == "aws":
        raise ProviderError("AWS provider is not yet implemented. Use 'provider: local' in kitefs.yaml.")
    raise ProviderError(f"Unknown provider '{config.provider}'. Supported providers: local.")
