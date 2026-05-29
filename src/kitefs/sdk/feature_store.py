from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kitefs.config import RuntimeConfig, load_runtime_config
from kitefs.errors import RegistryReadError
from kitefs.providers import Provider, build_provider
from kitefs.registry import (
    build_registry_document,
    discover_feature_groups,
    summarize_registry,
    validate_cross_definition,
)
from kitefs.registry import (
    describe_feature_group as _describe_feature_group,
)
from kitefs.sdk.results import ApplyResult, FeatureGroupDescription, FeatureGroupSummary


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

    def apply(self, *, publish: bool = False) -> ApplyResult:
        """Compile feature definitions into the local registry.

        Discovers all FeatureGroup instances in ./feature_store/definitions/*.py,
        validates them as a set, then atomically writes ./feature_store/registry.json.
        Returns an ApplyResult listing the registered group names sorted alphabetically.

        publish=True is reserved for a future remote-write feature and is accepted
        but has no effect in this implementation.
        """
        definitions_dir = Path.cwd() / "feature_store" / "definitions"
        groups = discover_feature_groups(definitions_dir)
        validate_cross_definition(groups)

        store = self._provider.registry_store()
        try:
            prior = store.read()
        except RegistryReadError as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                prior = {"feature_groups": {}}
            else:
                raise

        document = build_registry_document(
            groups,
            prior_document=prior,
            now=datetime.now(UTC),
        )
        store.write(document)

        return ApplyResult(
            registered_groups=sorted(g.name for g in groups),
            published=False,
        )

    def list_feature_groups(self) -> list[FeatureGroupSummary]:
        """Return a summary for each registered feature group, sorted alphabetically by name.

        Returns an empty list when the registry contains no groups.
        Raises RegistryReadError if the registry is missing or undecodable.
        """
        document = self._provider.registry_store().read()
        return summarize_registry(document)

    def describe_feature_group(self, name: str) -> FeatureGroupDescription:
        """Return the full description for the named feature group.

        Raises FeatureGroupNotFoundError if name is not in the registry.
        Raises RegistryReadError if the registry is missing or undecodable.
        """
        document = self._provider.registry_store().read()
        return _describe_feature_group(document, name)
