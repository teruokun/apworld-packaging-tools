# SPDX-License-Identifier: MIT
"""Build Island distributions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import click

from island_build import (
    BuildConfig,
    BuildConfigError,
    build_island,
    build_island_with_vendoring,
    build_sdist,
    IslandError,
    SdistError,
    extract_entry_points_from_pyproject,
    validate_entry_points,
    MissingEntryPointError,
    InvalidEntryPointError,
)

from ..config import CLIConfig, ConfigError, load_config
from ..main import echo_error, echo_info, echo_success, echo_warning, pass_context, Context


def _load_entry_points(pyproject_path: Path) -> dict[str, dict[str, str]] | None:
    """Load entry points from pyproject.toml.

    Args:
        pyproject_path: Path to pyproject.toml

    Returns:
        Entry points dictionary or None if not found
    """
    if not pyproject_path.exists():
        return None

    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
    except tomllib.TOMLDecodeError:
        return None

    return extract_entry_points_from_pyproject(pyproject)


@click.command()
@click.option(
    "--sdist/--no-sdist",
    default=False,
    help="Build source distribution (.tar.gz).",
)
@click.option(
    "--island/--no-island",
    "build_island_flag",
    default=True,
    help="Build binary distribution (.island).",
)
@click.option(
    "--vendor/--no-vendor",
    default=True,
    help="Vendor dependencies into the .island file.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default="dist",
    help="Output directory for built distributions.",
)
@click.option(
    "--source-dir",
    "-s",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Source directory (defaults to auto-detection).",
)
@pass_context
def build(
    ctx: Context,
    sdist: bool,
    build_island_flag: bool,
    vendor: bool,
    output_dir: Path,
    source_dir: Optional[Path],
) -> None:
    """Build Island distribution packages.

    By default, builds a .island binary distribution with vendored dependencies.
    Use --sdist to also build a source distribution.

    \b
    Examples:
        island build                    # Build .island only
        island build --sdist            # Build both .island and .tar.gz
        island build --no-vendor        # Build without vendoring dependencies
        island build -o ./output        # Output to custom directory
    """
    # Load configuration
    try:
        cli_config = ctx.load_config()
    except (ConfigError, FileNotFoundError) as e:
        echo_error(str(e))
        raise SystemExit(1)

    project_dir = cli_config.project_dir

    # Determine source directory
    if source_dir is None:
        source_dir = cli_config.source_dir
        if source_dir is None:
            # Try common locations
            for candidate in [
                project_dir / "src" / cli_config.name.replace("-", "_"),
                project_dir / cli_config.name.replace("-", "_"),
                project_dir / "src",
            ]:
                if candidate.exists():
                    source_dir = candidate
                    break

    if source_dir is None or not source_dir.exists():
        echo_error("Could not find source directory. Use --source-dir to specify.")
        raise SystemExit(1)

    # Resolve output directory
    if not output_dir.is_absolute():
        output_dir = project_dir / output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    echo_info(f"Building from: {source_dir}")
    echo_info(f"Output directory: {output_dir}")

    # Load build configuration
    try:
        pyproject_path = project_dir / "pyproject.toml"
        if pyproject_path.exists():
            build_config = BuildConfig.from_pyproject(pyproject_path, source_dir=source_dir)
        else:
            # Try legacy mode with archipelago.json
            manifest_path = project_dir / "archipelago.json"
            if manifest_path.exists():
                build_config = BuildConfig.from_manifest(manifest_path, source_dir=source_dir)
                echo_warning("Using legacy archipelago.json. Consider migrating to pyproject.toml.")
            else:
                echo_error("No pyproject.toml or archipelago.json found")
                raise SystemExit(1)
    except BuildConfigError as e:
        echo_error(f"Configuration error: {e}")
        raise SystemExit(1)

    if ctx.verbose:
        echo_info(f"Package: {build_config.name} v{build_config.version}")
        echo_info(f"Game: {build_config.game_name}")
        if build_config.dependencies:
            echo_info(f"Dependencies: {', '.join(build_config.dependencies)}")

    # Extract entry points from pyproject.toml
    entry_points = _load_entry_points(pyproject_path) if pyproject_path.exists() else None

    # Validate entry points for island format
    if build_island_flag and entry_points:
        try:
            validate_entry_points(entry_points)
            if ctx.verbose:
                ap_island_eps = entry_points.get("ap-island", {})
                echo_info(f"Entry points: {len(ap_island_eps)} ap-island entry point(s)")
        except (MissingEntryPointError, InvalidEntryPointError) as e:
            echo_error(f"Entry point validation failed: {e}")
            raise SystemExit(1)
    elif build_island_flag and not entry_points:
        echo_warning("No entry points found. Island packages should have ap-island entry points.")

    built_files: list[str] = []

    # Build source distribution
    if sdist:
        echo_info("\nBuilding source distribution...")
        try:
            result = build_sdist(build_config, output_dir=output_dir, source_dir=source_dir)
            echo_success(f"  Created: {result.filename} ({result.size:,} bytes)")
            echo_info(f"  Files included: {len(result.files_included)}")
            built_files.append(str(result.path))
        except SdistError as e:
            echo_error(f"Failed to build source distribution: {e}")
            raise SystemExit(1)

    # Build binary distribution
    if build_island_flag:
        echo_info("\nBuilding binary distribution (.island)...")
        try:
            if vendor and build_config.dependencies:
                echo_info("  Vendoring dependencies...")
                result = build_island_with_vendoring(
                    build_config,
                    output_dir=output_dir,
                    source_dir=source_dir,
                    entry_points=entry_points,
                )
            else:
                result = build_island(
                    build_config,
                    output_dir=output_dir,
                    source_dir=source_dir,
                    entry_points=entry_points,
                )

            echo_success(f"  Created: {result.filename} ({result.size:,} bytes)")
            echo_info(f"  Files included: {len(result.files_included)}")
            echo_info(f"  Platform: {result.platform_tag}")
            echo_info(f"  Pure Python: {result.is_pure_python}")
            built_files.append(str(result.path))

            if ctx.verbose:
                echo_info("\n  Manifest:")
                for key, value in result.manifest.items():
                    echo_info(f"    {key}: {value}")

        except IslandError as e:
            echo_error(f"Failed to build .island: {e}")
            raise SystemExit(1)
        except ImportError as e:
            if "island_vendor" in str(e):
                echo_error(
                    "Vendoring requires island-vendor package. Install it or use --no-vendor."
                )
            else:
                echo_error(f"Import error: {e}")
            raise SystemExit(1)

    if not built_files:
        echo_warning("No distributions were built. Use --island or --sdist.")
        raise SystemExit(1)

    echo_success(f"\nBuild complete! {len(built_files)} distribution(s) created.")
