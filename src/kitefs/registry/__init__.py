"""Registry package — definition discovery, validation, serialization, and lifecycle management."""

from kitefs.registry._discovery import _discover_definitions
from kitefs.registry._manager import ApplyResult, RegistryManager
from kitefs.registry._validation import _validate_definitions

__all__ = [
    "ApplyResult",
    "RegistryManager",
    "_discover_definitions",
    "_validate_definitions",
]
