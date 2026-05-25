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
