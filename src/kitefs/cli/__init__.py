import sys
import traceback

import click

from kitefs.errors import KiteFSError


@click.group()
def main() -> None:
    """KiteFS command-line interface."""


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
