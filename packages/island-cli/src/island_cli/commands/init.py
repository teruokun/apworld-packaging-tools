# SPDX-License-Identifier: MIT
"""Initialize a new Island project."""

from __future__ import annotations

import re
from pathlib import Path

import click

from ..main import echo_error, echo_info, echo_success
from ..template_engine import TemplateEngine, TemplateError


def normalize_name(name: str) -> str:
    """Normalize a name to a valid Python package name."""
    # Convert to lowercase
    name = name.lower()
    # Replace spaces and hyphens with underscores
    name = re.sub(r"[\s-]+", "_", name)
    # Remove invalid characters
    name = re.sub(r"[^a-z0-9_]", "", name)
    # Ensure it doesn't start with a number
    if name and name[0].isdigit():
        name = "_" + name
    return name


def to_class_name(name: str) -> str:
    """Convert a name to a valid Python class name (PascalCase)."""
    # Split on spaces, hyphens, and underscores
    parts = re.split(r"[\s_-]+", name)
    # Capitalize each part
    return "".join(part.capitalize() for part in parts if part)


@click.command()
@click.argument("name")
@click.option(
    "--game",
    help="Display name of the game (defaults to NAME in title case).",
)
@click.option(
    "--author",
    default="Your Name",
    help="Author name for the package.",
)
@click.option(
    "--description",
    default="",
    help="Short description of the Island package.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (defaults to current directory).",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing files.",
)
def init(
    name: str,
    game: str | None,
    author: str,
    description: str,
    output_dir: Path | None,
    force: bool,
) -> None:
    """Initialize a new Island project.

    NAME is the package name (e.g., 'pokemon-emerald' or 'my_game').

    \b
    This command creates:
      - pyproject.toml with [tool.island] configuration
      - src/{name}/__init__.py
      - src/{name}/world.py with a basic World implementation
      - tests/ directory with test scaffolding
      - README.md

    \b
    Examples:
        island init pokemon-emerald
        island init my-game --game "My Awesome Game" --author "Developer"
    """
    # Normalize the package name
    package_name = normalize_name(name)
    if not package_name:
        echo_error("Invalid package name")
        raise SystemExit(1)

    # Determine game display name
    if not game:
        game = name.replace("-", " ").replace("_", " ").title()

    # Generate class name
    class_name = to_class_name(game)

    # Default description
    if not description:
        description = f"Archipelago randomizer implementation for {game}"

    # Determine output directory
    if output_dir is None:
        output_dir = Path.cwd() / package_name
    else:
        output_dir = output_dir / package_name

    # Check if directory exists
    if output_dir.exists() and not force:
        echo_error(f"Directory already exists: {output_dir}")
        echo_info("Use --force to overwrite existing files")
        raise SystemExit(1)

    echo_info(f"Creating Island project: {game}")
    echo_info(f"  Package name: {package_name}")
    echo_info(f"  Output directory: {output_dir}")

    # Template variables
    template_vars = {
        "name": name.lower().replace("_", "-"),
        "package_name": package_name,
        "game": game,
        "game_lower": game.lower().replace(" ", "-"),
        "class_name": class_name,
        "author": author,
        "description": description,
    }

    # Locate template directory
    template_dir = Path(__file__).parent.parent / "templates" / "island"

    try:
        engine = TemplateEngine(template_dir)
        created_files = engine.render(output_dir, template_vars, force=force)

        # Report created files
        for file_path in created_files:
            echo_info(f"  Created: {file_path}")

    except TemplateError as e:
        echo_error(f"Template error: {e}")
        raise SystemExit(1) from e

    echo_success("\nIsland project created successfully!")
    echo_info("\nNext steps:")
    echo_info(f"  cd {output_dir}")
    echo_info(f"  # Edit src/{package_name}/world.py to implement your game")
    echo_info("  island build  # Build the .island file")
