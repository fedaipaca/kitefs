"""SDK entry point — orchestrates all KiteFS operations through a single class."""

from pathlib import Path

from kitefs.config import load_config
from kitefs.exceptions import ConfigurationError
from kitefs.providers.factory import create_provider
from kitefs.registry import ApplyResult, RegistryManager


class FeatureStore:
    """Root SDK class that wires configuration, provider, and managers.

    Instantiate with an explicit project root or let the constructor walk
    up from the current working directory to find ``kitefs.yaml``.
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        """Initialise the feature store from a KiteFS project directory.

        If *project_root* is provided, use it directly. Otherwise walk up
        from ``cwd`` to locate ``kitefs.yaml``.
        """
        resolved_root = self._resolve_project_root(project_root)

        config = load_config(resolved_root)
        provider = create_provider(config)
        self._registry_manager = RegistryManager(provider, config.definitions_path)

    def apply(self) -> ApplyResult:
        """Register all feature group definitions into the registry."""
        return self._registry_manager.apply()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_project_root(project_root: str | Path | None) -> Path:
        """Resolve the project root to a concrete directory containing kitefs.yaml."""
        if project_root is not None:
            root = Path(project_root).resolve()
            if not (root / "kitefs.yaml").exists():
                raise ConfigurationError("No KiteFS project found. Run `kitefs init` to create one.")
            return root

        # Walk upward from cwd until kitefs.yaml is found.
        current = Path.cwd().resolve()
        while True:
            if (current / "kitefs.yaml").exists():
                return current
            parent = current.parent
            if parent == current:
                # Reached filesystem root without finding a project.
                raise ConfigurationError("No KiteFS project found. Run `kitefs init` to create one.")
            current = parent
