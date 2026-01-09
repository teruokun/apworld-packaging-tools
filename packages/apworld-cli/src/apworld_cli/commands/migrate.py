# SPDX-License-Identifier: MIT
"""Migrate legacy archipelago.json to modern schema."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

import click

from apworld_manifest import (
    CURRENT_SCHEMA_VERSION,
    MIN_COMPATIBLE_VERSION,
    MANIFEST_DEFAULTS,
    validate_manifest,
)

from ..main import echo_error, echo_info, echo_success, echo_warning, pass_context, Context


PYPROJECT_TEMPLATE = """[build-system]
requires = ["hatchling", "apworld-build"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "{version}"
description = "{description}"
readme = "README.md"
{license_line}requires-python = ">=3.10"
{authors_section}keywords = {keywords}
dependencies = []

[project.urls]
{urls_section}

[tool.apworld]
game = "{game}"
{ap_version_section}

[tool.apworld.vendor]
exclude = ["typing_extensions"]

[tool.hatch.build.targets.wheel]
packages = ["src/{package_name}"]
"""


def _normalize_name(name: str) -> str:
    """Normalize a name to a valid Python package name."""
    name = name.lower()
    name = re.sub(r"[\s-]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    if name and name[0].isdigit():
        name = "_" + name
    return name


def _migrate_manifest(legacy: dict[str, Any]) -> dict[str, Any]:
    """Migrate a legacy manifest to the modern schema.

    Args:
        legacy: Legacy archipelago.json content

    Returns:
        Migrated manifest with modern schema
    """
    migrated: dict[str, Any] = {}

    # Required fields
    migrated["game"] = legacy.get("game", "Unknown Game")
    migrated["version"] = CURRENT_SCHEMA_VERSION
    migrated["compatible_version"] = legacy.get("compatible_version", MIN_COMPATIBLE_VERSION)

    # Optional fields - copy if present
    if "world_version" in legacy:
        migrated["world_version"] = legacy["world_version"]
    elif "data_version" in legacy:
        # Some legacy manifests use data_version
        migrated["world_version"] = str(legacy["data_version"])

    if "minimum_ap_version" in legacy:
        migrated["minimum_ap_version"] = legacy["minimum_ap_version"]

    if "maximum_ap_version" in legacy:
        migrated["maximum_ap_version"] = legacy["maximum_ap_version"]

    if "authors" in legacy:
        migrated["authors"] = legacy["authors"]

    if "description" in legacy:
        migrated["description"] = legacy["description"]

    if "license" in legacy:
        migrated["license"] = legacy["license"]

    if "homepage" in legacy:
        migrated["homepage"] = legacy["homepage"]

    if "repository" in legacy:
        migrated["repository"] = legacy["repository"]

    if "keywords" in legacy:
        migrated["keywords"] = legacy["keywords"]

    if "platforms" in legacy:
        migrated["platforms"] = legacy["platforms"]

    if "pure_python" in legacy:
        migrated["pure_python"] = legacy["pure_python"]

    if "vendored_dependencies" in legacy:
        migrated["vendored_dependencies"] = legacy["vendored_dependencies"]

    # Apply defaults for missing optional fields
    for key, default_value in MANIFEST_DEFAULTS.items():
        if key not in migrated:
            if isinstance(default_value, (list, dict)):
                migrated[key] = default_value.copy()
            else:
                migrated[key] = default_value

    return migrated


def _generate_pyproject(manifest: dict[str, Any], package_name: str) -> str:
    """Generate pyproject.toml content from a manifest.

    Args:
        manifest: Migrated manifest
        package_name: Normalized package name

    Returns:
        pyproject.toml content as string
    """
    game = manifest.get("game", "Unknown Game")
    version = manifest.get("world_version", "0.1.0")
    description = manifest.get("description", f"Archipelago implementation for {game}")

    # License line
    license_text = manifest.get("license", "")
    license_line = f'license = {{text = "{license_text}"}}\n' if license_text else ""

    # Authors section
    authors = manifest.get("authors", [])
    if authors:
        authors_lines = []
        for author in authors:
            authors_lines.append(f'    {{name = "{author}"}}')
        authors_section = "authors = [\n" + ",\n".join(authors_lines) + "\n]\n"
    else:
        authors_section = ""

    # Keywords
    keywords = manifest.get("keywords", [])
    keywords_str = json.dumps(keywords)

    # URLs section
    urls_lines = []
    if manifest.get("homepage"):
        urls_lines.append(f'Homepage = "{manifest["homepage"]}"')
    if manifest.get("repository"):
        urls_lines.append(f'Repository = "{manifest["repository"]}"')
    if not urls_lines:
        urls_lines.append('Homepage = "https://github.com/ArchipelagoMW/Archipelago"')
    urls_section = "\n".join(urls_lines)

    # AP version section
    ap_version_lines = []
    if manifest.get("minimum_ap_version"):
        ap_version_lines.append(f'minimum_ap_version = "{manifest["minimum_ap_version"]}"')
    if manifest.get("maximum_ap_version"):
        ap_version_lines.append(f'maximum_ap_version = "{manifest["maximum_ap_version"]}"')
    ap_version_section = "\n".join(ap_version_lines)

    return PYPROJECT_TEMPLATE.format(
        name=package_name.replace("_", "-"),
        package_name=package_name,
        version=version,
        description=description,
        license_line=license_line,
        authors_section=authors_section,
        keywords=keywords_str,
        urls_section=urls_section,
        game=game,
        ap_version_section=ap_version_section,
    )


@click.command()
@click.option(
    "--input",
    "-i",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    help="Path to legacy archipelago.json (defaults to current directory).",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    help="Output path for migrated manifest (defaults to overwriting input).",
)
@click.option(
    "--generate-pyproject",
    is_flag=True,
    help="Also generate a pyproject.toml file.",
)
@click.option(
    "--pyproject-output",
    type=click.Path(path_type=Path),
    help="Output path for pyproject.toml (defaults to same directory as manifest).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without writing files.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing files.",
)
@pass_context
def migrate(
    ctx: Context,
    input_path: Optional[Path],
    output_path: Optional[Path],
    generate_pyproject: bool,
    pyproject_output: Optional[Path],
    dry_run: bool,
    force: bool,
) -> None:
    """Migrate legacy archipelago.json to modern schema.

    Reads a legacy archipelago.json file and updates it to the modern schema
    with appropriate defaults. Optionally generates a pyproject.toml file.

    \b
    Examples:
        apworld migrate                          # Migrate in current directory
        apworld migrate -i old/archipelago.json  # Migrate specific file
        apworld migrate --generate-pyproject     # Also create pyproject.toml
        apworld migrate --dry-run                # Preview changes
    """
    # Determine input path
    if input_path is None:
        project_dir = ctx.project_dir or Path.cwd()
        input_path = project_dir / "archipelago.json"

    if not input_path.exists():
        echo_error(f"Manifest not found: {input_path}")
        raise SystemExit(1)

    echo_info(f"Reading: {input_path}")

    # Read legacy manifest
    try:
        with open(input_path) as f:
            legacy_manifest = json.load(f)
    except json.JSONDecodeError as e:
        echo_error(f"Invalid JSON: {e}")
        raise SystemExit(1)

    # Check if already modern
    if legacy_manifest.get("version") == CURRENT_SCHEMA_VERSION:
        echo_warning("Manifest already uses modern schema version.")
        if not force:
            echo_info("Use --force to re-migrate anyway.")
            return

    # Migrate manifest
    echo_info("Migrating to modern schema...")
    migrated = _migrate_manifest(legacy_manifest)

    # Validate migrated manifest
    result = validate_manifest(migrated)
    if not result.valid:
        echo_error("Migration produced invalid manifest:")
        for error in result.errors:
            echo_error(f"  [{error.field}]: {error.message}")
        raise SystemExit(1)

    echo_success("  Migration successful!")

    # Show changes
    if ctx.verbose or dry_run:
        echo_info("\nMigrated manifest:")
        echo_info(json.dumps(migrated, indent=2))

    # Determine output path
    if output_path is None:
        output_path = input_path

    # Generate pyproject.toml if requested
    pyproject_content: Optional[str] = None
    if generate_pyproject:
        game = migrated.get("game", "Unknown")
        package_name = _normalize_name(game)
        pyproject_content = _generate_pyproject(migrated, package_name)

        if pyproject_output is None:
            pyproject_output = input_path.parent / "pyproject.toml"

        if ctx.verbose or dry_run:
            echo_info("\nGenerated pyproject.toml:")
            echo_info(pyproject_content)

    # Write files
    if dry_run:
        echo_warning("\nDry run - no files written.")
        echo_info(f"Would write: {output_path}")
        if pyproject_content:
            echo_info(f"Would write: {pyproject_output}")
        return

    # Check for existing files
    if output_path.exists() and output_path != input_path and not force:
        echo_error(f"Output file exists: {output_path}")
        echo_info("Use --force to overwrite.")
        raise SystemExit(1)

    if pyproject_output and pyproject_output.exists() and not force:
        echo_error(f"pyproject.toml already exists: {pyproject_output}")
        echo_info("Use --force to overwrite.")
        raise SystemExit(1)

    # Write migrated manifest
    with open(output_path, "w") as f:
        json.dump(migrated, f, indent=2)
    echo_success(f"Wrote: {output_path}")

    # Write pyproject.toml
    if pyproject_content and pyproject_output:
        with open(pyproject_output, "w") as f:
            f.write(pyproject_content)
        echo_success(f"Wrote: {pyproject_output}")

    echo_success("\nMigration complete!")

    if generate_pyproject:
        echo_info("\nNext steps:")
        echo_info("  1. Review and customize pyproject.toml")
        echo_info("  2. Run 'apworld validate' to verify")
        echo_info("  3. Run 'apworld build' to create distributions")
