"""CLI entry point for KiteFS — thin delegation layer over the SDK.

``kitefs init`` is the only self-contained command because the project
scaffold (including ``kitefs.yaml``) does not exist yet when it runs.
All other commands delegate to :class:`kitefs.FeatureStore`.
"""

import json
from pathlib import Path

import click

_GITIGNORE_ENTRY = "feature_store/data/"

_DEFAULT_CONFIG = """\
provider: local
storage_root: ./feature_store/
"""

_EXAMPLE_FEATURES = '''\
"""Example feature group definitions for KiteFS.

Uncomment and modify the example below, then run ``kitefs apply``
to register your feature groups.
"""

# from kitefs import (
#     EntityKey,
#     EventTimestamp,
#     Expect,
#     Feature,
#     FeatureGroup,
#     FeatureType,
#     Metadata,
#     StorageTarget,
#     ValidationMode,
# )
#
# example_features = FeatureGroup(
#     name="example_features",
#     storage_target=StorageTarget.OFFLINE,
#     entity_key=EntityKey(name="entity_id", dtype=FeatureType.INTEGER),
#     event_timestamp=EventTimestamp(name="event_timestamp", dtype=FeatureType.DATETIME),
#     features=[
#         Feature(name="feature_one", dtype=FeatureType.FLOAT, expect=Expect().not_null()),
#         Feature(name="feature_two", dtype=FeatureType.STRING),
#     ],
#     ingestion_validation=ValidationMode.ERROR,
#     metadata=Metadata(owner="your-team", description="An example feature group."),
# )
'''

_SEED_REGISTRY = {"version": "1.0", "feature_groups": {}}


@click.group()
def cli() -> None:
    """KiteFS — a Python feature store for offline/online feature storage and serving."""


@cli.command()
@click.argument("path", required=False, default=None, type=click.Path(file_okay=False))
def init(path: str | None) -> None:
    """Create a new KiteFS project at PATH (default: current directory)."""
    project_root = Path(path).resolve() if path else Path.cwd().resolve()
    config_path = project_root / "kitefs.yaml"

    if config_path.exists():
        click.echo("Error: KiteFS project already initialized at this location.", err=True)
        raise SystemExit(1)

    storage_root = project_root / "feature_store"

    try:
        # Create directory structure
        (storage_root / "definitions").mkdir(parents=True, exist_ok=True)
        (storage_root / "data" / "offline_store").mkdir(parents=True, exist_ok=True)
        (storage_root / "data" / "online_store").mkdir(parents=True, exist_ok=True)

        # Seed definitions
        (storage_root / "definitions" / "__init__.py").write_text("", encoding="utf-8")
        (storage_root / "definitions" / "example_features.py").write_text(_EXAMPLE_FEATURES, encoding="utf-8")

        # Seed registry.json — deterministic output for meaningful Git diffs
        registry_path = storage_root / "registry.json"
        registry_path.write_text(json.dumps(_SEED_REGISTRY, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        # Create or append .gitignore — check by exact line, not substring, to avoid
        # false positives from comments or negated rules containing the entry.
        gitignore_path = project_root / ".gitignore"
        if gitignore_path.exists():
            content = gitignore_path.read_text(encoding="utf-8")
            existing_lines = {line.strip() for line in content.splitlines()}
            if _GITIGNORE_ENTRY not in existing_lines:
                with gitignore_path.open("a", encoding="utf-8") as f:
                    if content and not content.endswith("\n"):
                        f.write("\n")
                    f.write(_GITIGNORE_ENTRY + "\n")
        else:
            gitignore_path.write_text(_GITIGNORE_ENTRY + "\n", encoding="utf-8")

        # Seed kitefs.yaml last — this is the sentinel file that guards against
        # re-init. Writing it last ensures a crash mid-scaffold leaves no sentinel,
        # so the user can retry `kitefs init` without manual cleanup.
        config_path.write_text(_DEFAULT_CONFIG, encoding="utf-8")
    except OSError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None

    click.echo(f"Project initialized at {project_root}")
    click.echo("  Provider: local")
    click.echo(f"  Config:   {config_path}")


@cli.command()
def apply() -> None:
    """Register feature group definitions into the registry."""
    from kitefs.exceptions import KiteFSError
    from kitefs.feature_store import FeatureStore

    try:
        fs = FeatureStore()
        result = fs.apply()
    except KiteFSError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None

    click.echo(f"Applied {result.group_count} feature group(s) — registered successfully.")
