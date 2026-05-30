import sys
import traceback

import click

from kitefs.errors import KiteFSError


@click.group()
def main() -> None:
    """KiteFS command-line interface."""


@main.command()
def init() -> None:
    """Scaffold a new KiteFS producer project in the current directory."""
    from pathlib import Path

    from kitefs.cli import scaffold

    click.echo(scaffold.init_producer(Path.cwd()))


@main.command(name="init-config")
def init_config() -> None:
    """Create a consumer-only KiteFS configuration in the current directory."""
    from pathlib import Path

    from kitefs.cli import scaffold

    click.echo(scaffold.init_config(Path.cwd()))


def _emit_or_write(rendered: str, output: str | None) -> None:
    """Echo rendered to stdout, or write it to a file; OSError is wrapped as ClickException."""
    if output is None:
        click.echo(rendered)
        return
    from pathlib import Path

    try:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Could not write output to {output}: {exc}") from exc


@main.command(name="list")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: text (default) or json.",
)
@click.option(
    "--output",
    "output",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write output to this file path instead of stdout.",
)
def list_(fmt: str, output: str | None) -> None:
    """List registered feature groups."""
    from kitefs.cli import render
    from kitefs.sdk.feature_store import FeatureStore

    summaries = FeatureStore().list_feature_groups()
    rendered = render.render_list(summaries, as_json=(fmt == "json"))
    _emit_or_write(rendered, output)


@main.command()
@click.argument("name")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: text (default) or json.",
)
@click.option(
    "--output",
    "output",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write output to this file path instead of stdout.",
)
def describe(name: str, fmt: str, output: str | None) -> None:
    """Show full details for a registered feature group."""
    from kitefs.cli import render
    from kitefs.sdk.feature_store import FeatureStore

    description = FeatureStore().describe_feature_group(name)
    rendered = render.render_describe(description, as_json=(fmt == "json"))
    _emit_or_write(rendered, output)


@main.command()
@click.option("--publish", is_flag=True, help="Publish to the configured remote registry.")
@click.option("--no-confirm", "no_confirm", is_flag=True, help="Skip the publish confirmation prompt.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: text (default) or json.",
)
def apply(publish: bool, no_confirm: bool, fmt: str) -> None:
    """Compile feature definitions into the local registry."""
    if publish and not no_confirm:
        click.echo("You are about to publish the registry to the remote target.", err=True)
        click.echo("This overwrites the existing remote registry.", err=True)
        click.echo("Type 'yes' to continue: ", err=True, nl=False)
        response = sys.stdin.readline().rstrip("\n")
        if response != "yes":
            raise click.ClickException("Publish aborted.")

    from kitefs.cli import render
    from kitefs.sdk.feature_store import FeatureStore

    result = FeatureStore().apply(publish=publish)
    click.echo(render.render_apply(result, as_json=(fmt == "json")))


@main.command()
@click.argument("group_name")
@click.argument("path")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: text (default) or json.",
)
def ingest(group_name: str, path: str, fmt: str) -> None:
    """Append validated feature rows to the offline store."""
    from pathlib import Path as _Path

    suffix = _Path(path).suffix.lower()
    if suffix not in {".csv", ".parquet"}:
        from kitefs.errors import IngestionShapeError, format_actionable

        raise IngestionShapeError(
            format_actionable(
                group=group_name,
                problem=f"unsupported file extension {suffix!r}; only .csv and .parquet are accepted",
                next_step="provide a .csv or .parquet file path",
            )
        )

    from kitefs.cli import render
    from kitefs.sdk.feature_store import FeatureStore

    result = FeatureStore().ingest(group_name, path)
    click.echo(render.render_ingest(result, as_json=(fmt == "json")))


@main.command()
@click.argument("group_name", required=False, default=None)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: text (default) or json.",
)
def materialize(group_name: str | None, fmt: str) -> None:
    """Populate the online store from the latest offline rows."""
    from kitefs.cli import render
    from kitefs.sdk.feature_store import FeatureStore

    result = FeatureStore().materialize(group_name)
    click.echo(render.render_materialize(result, as_json=(fmt == "json")))
    if result.failed:
        raise SystemExit(1)


def cli() -> None:
    """Console-script entry point; outermost CLI error boundary."""
    try:
        main()
    except KiteFSError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        traceback.print_exception(e, file=sys.stderr)
        sys.exit(2)
