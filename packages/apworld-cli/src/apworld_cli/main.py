# SPDX-License-Identifier: MIT
"""CLI entry point for apworld command."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from .config import CLIConfig, ConfigError, find_project_root, load_config


class Context:
    """CLI context object passed to commands."""

    def __init__(self) -> None:
        self.config: Optional[CLIConfig] = None
        self.verbose: bool = False
        self.project_dir: Optional[Path] = None

    def load_config(self) -> CLIConfig:
        """Load configuration, caching the result."""
        if self.config is None:
            self.config = load_config(self.project_dir)
        return self.config


pass_context = click.make_pass_decorator(Context, ensure=True)


def echo_error(message: str) -> None:
    """Print an error message to stderr."""
    click.secho(f"Error: {message}", fg="red", err=True)


def echo_success(message: str) -> None:
    """Print a success message."""
    click.secho(message, fg="green")


def echo_info(message: str) -> None:
    """Print an info message."""
    click.echo(message)


def echo_warning(message: str) -> None:
    """Print a warning message."""
    click.secho(f"Warning: {message}", fg="yellow", err=True)


@click.group()
@click.version_option()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output.",
)
@click.option(
    "-C",
    "--directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Change to directory before running command.",
)
@pass_context
def cli(ctx: Context, verbose: bool, directory: Optional[Path]) -> None:
    """APWorld package management tool.

    Build, validate, and publish APWorld packages for Archipelago.

    \b
    Examples:
        apworld init my-game
        apworld build
        apworld validate
        apworld publish
        apworld migrate --generate-pyproject
    """
    ctx.verbose = verbose
    ctx.project_dir = directory


# Import and register commands
from .commands import init, build, validate, publish, migrate

cli.add_command(init.init)
cli.add_command(build.build)
cli.add_command(validate.validate)
cli.add_command(publish.publish)
cli.add_command(migrate.migrate)


def main() -> None:
    """Main entry point for the CLI."""
    try:
        cli()
    except ConfigError as e:
        echo_error(str(e))
        sys.exit(1)
    except FileNotFoundError as e:
        echo_error(str(e))
        sys.exit(1)
    except Exception as e:
        echo_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
