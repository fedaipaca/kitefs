from __future__ import annotations

from pathlib import Path

from kitefs.config import RuntimeConfig, load_runtime_config
from kitefs.providers import Provider, build_provider


class FeatureStore:
    """User-facing SDK entry point.

    Reads ./kitefs.yaml from the current working directory, resolves the
    runtime target, and wires up the matching provider.
    """

    def __init__(self) -> None:
        root = Path.cwd()
        self._config: RuntimeConfig = load_runtime_config(root)
        self._provider: Provider = build_provider(self._config, root)

    @property
    def runtime_target(self) -> str:
        """Resolved runtime target: 'local' or 'remote'."""
        return self._config.target
