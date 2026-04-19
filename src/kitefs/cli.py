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


@cli.command(name="list")
@click.option("--format", "fmt", default=None, type=click.Choice(["json"], case_sensitive=False), help="Output format.")
@click.option("--target", default=None, type=click.Path(), help="File path to write output to.")
def list_cmd(fmt: str | None, target: str | None) -> None:
    """List all registered feature groups with summary information."""
    from kitefs.exceptions import KiteFSError
    from kitefs.feature_store import FeatureStore

    try:
        fs = FeatureStore()
        result = fs.list_feature_groups(format=fmt, target=target)
    except KiteFSError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None

    if target is not None:
        click.echo(f"Output written to {target}")
        return

    if fmt == "json":
        click.echo(result)
        return

    # Default: human-readable table.
    assert isinstance(result, list)  # target/format branches already returned
    if not result:
        click.echo("No feature groups registered. Run `kitefs apply` first.")
        return

    _render_list_table(result)


def _render_list_table(summaries: list[dict]) -> None:
    """Render feature group summaries as a human-readable table."""
    headers = ["Name", "Owner", "Entity Key", "Storage Target", "Features"]
    keys = ["name", "owner", "entity_key", "storage_target", "feature_count"]

    rows: list[list[str]] = []
    for s in summaries:
        rows.append([str(s.get(k) or "") for k in keys])

    # Compute column widths from headers and data.
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    click.echo(_fmt_row(headers))
    click.echo("  ".join("-" * w for w in widths))
    for row in rows:
        click.echo(_fmt_row(row))


@cli.command()
@click.argument("feature_group_name")
@click.option("--format", "fmt", default=None, type=click.Choice(["json"], case_sensitive=False), help="Output format.")
@click.option("--target", default=None, type=click.Path(), help="File path to write output to.")
def describe(feature_group_name: str, fmt: str | None, target: str | None) -> None:
    """Display the full definition of a specific feature group."""
    from kitefs.exceptions import KiteFSError
    from kitefs.feature_store import FeatureStore

    try:
        fs = FeatureStore()
        result = fs.describe_feature_group(feature_group_name, format=fmt, target=target)
    except KiteFSError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None

    if target is not None:
        click.echo(f"Output written to {target}")
        return

    if fmt == "json":
        click.echo(result)
        return

    # Default: human-readable key-value layout.
    assert isinstance(result, dict)  # target/format branches already returned
    _render_describe(result)


def _render_describe(entry: dict) -> None:
    """Render a full feature group definition as a human-readable layout."""
    click.echo(f"Feature Group: {entry.get('name', '?')}")
    click.echo(f"  Storage Target:              {entry.get('storage_target', '?')}")

    ek = entry.get("entity_key", {})
    click.echo(f"  Entity Key:                  {ek.get('name', '?')} ({ek.get('dtype', '?')})")

    et = entry.get("event_timestamp", {})
    click.echo(f"  Event Timestamp:             {et.get('name', '?')} ({et.get('dtype', '?')})")

    click.echo(f"  Ingestion Validation:        {entry.get('ingestion_validation', '?')}")
    click.echo(f"  Offline Retrieval Validation: {entry.get('offline_retrieval_validation', '?')}")

    meta = entry.get("metadata") or {}
    if meta.get("owner"):
        click.echo(f"  Owner:                       {meta['owner']}")
    if meta.get("description"):
        click.echo(f"  Description:                 {meta['description']}")
    if meta.get("tags"):
        click.echo(f"  Tags:                        {meta['tags']}")

    click.echo(f"  Applied At:                  {entry.get('applied_at', '?')}")
    click.echo(f"  Last Materialized At:        {entry.get('last_materialized_at', 'None')}")

    features = entry.get("features", [])
    click.echo(f"  Features ({len(features)}):")
    for f in features:
        expect_str = ""
        if f.get("expect"):
            expect_str = f" expect={f['expect']}"
        click.echo(f"    - {f['name']} ({f.get('dtype', '?')}){expect_str}")

    join_keys = entry.get("join_keys", [])
    if join_keys:
        click.echo(f"  Join Keys ({len(join_keys)}):")
        for jk in join_keys:
            click.echo(f"    - {jk['field_name']} -> {jk['referenced_group']}")
