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
    if output is not None:
        from pathlib import Path

        Path(output).write_text(rendered + "\n", encoding="utf-8")
    else:
        click.echo(rendered)


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
    if output is not None:
        from pathlib import Path

        Path(output).write_text(rendered + "\n", encoding="utf-8")
    else:
        click.echo(rendered)


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
