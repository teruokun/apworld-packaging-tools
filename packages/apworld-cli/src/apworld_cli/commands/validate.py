# SPDX-License-Identifier: MIT
"""Validate APWorld manifest and package structure."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import click

from apworld_manifest import (
    validate_manifest,
    transform_pyproject,
    ManifestTransformError,
)
from apworld_version import is_valid_semver

from ..config import ConfigError
from ..main import echo_error, echo_info, echo_success, echo_warning, pass_context, Context


def _validate_package_structure(project_dir: Path, package_name: str) -> list[str]:
    """Validate the package directory structure.

    Returns a list of warnings/errors found.
    """
    issues: list[str] = []

    # Check for source directory
    src_candidates = [
        project_dir / "src" / package_name,
        project_dir / package_name,
    ]

    source_dir = None
    for candidate in src_candidates:
        if candidate.exists():
            source_dir = candidate
            break

    if source_dir is None:
        issues.append(
            f"Source directory not found. Expected: src/{package_name}/ or {package_name}/"
        )
        return issues

    # Check for __init__.py
    init_file = source_dir / "__init__.py"
    if not init_file.exists():
        issues.append(f"Missing __init__.py in {source_dir}")

    # Check for world.py or similar
    world_files = list(source_dir.glob("*world*.py")) + list(source_dir.glob("*World*.py"))
    if not world_files:
        issues.append(f"No world implementation file found in {source_dir}")

    return issues


def _check_version_format(version: str) -> list[str]:
    """Check if version follows semantic versioning."""
    issues: list[str] = []

    if not version:
        issues.append("Version is empty")
        return issues

    if not is_valid_semver(version):
        issues.append(
            f"Version '{version}' does not follow semantic versioning (MAJOR.MINOR.PATCH)"
        )

    return issues


@click.command()
@click.option(
    "--manifest",
    "-m",
    type=click.Path(exists=True, path_type=Path),
    help="Path to archipelago.json manifest to validate.",
)
@click.option(
    "--pyproject",
    "-p",
    type=click.Path(exists=True, path_type=Path),
    help="Path to pyproject.toml to validate.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as errors.",
)
@click.option(
    "--check-structure",
    is_flag=True,
    default=True,
    help="Also validate package directory structure.",
)
@pass_context
def validate(
    ctx: Context,
    manifest: Optional[Path],
    pyproject: Optional[Path],
    strict: bool,
    check_structure: bool,
) -> None:
    """Validate manifest and package structure.

    Validates the archipelago.json manifest against the schema, checks version
    format, and optionally verifies the package directory structure.

    \b
    Examples:
        apworld validate                     # Validate current project
        apworld validate -m archipelago.json # Validate specific manifest
        apworld validate --strict            # Treat warnings as errors
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Determine what to validate
    project_dir = ctx.project_dir or Path.cwd()

    if manifest is None and pyproject is None:
        # Auto-detect
        pyproject_path = project_dir / "pyproject.toml"
        manifest_path = project_dir / "archipelago.json"

        if pyproject_path.exists():
            pyproject = pyproject_path
        elif manifest_path.exists():
            manifest = manifest_path
        else:
            echo_error("No pyproject.toml or archipelago.json found in current directory")
            raise SystemExit(1)

    manifest_data: dict = {}
    package_name: str = ""

    # Validate pyproject.toml
    if pyproject is not None:
        echo_info(f"Validating: {pyproject}")

        try:
            with open(pyproject, "rb") as f:
                pyproject_data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            errors.append(f"Invalid TOML syntax: {e}")
            pyproject_data = {}

        if pyproject_data:
            # Check required fields
            project_section = pyproject_data.get("project", {})

            if not project_section.get("name"):
                errors.append("Missing required field: [project].name")
            else:
                package_name = project_section["name"].replace("-", "_")

            if not project_section.get("version"):
                errors.append("Missing required field: [project].version")
            else:
                version_issues = _check_version_format(project_section["version"])
                errors.extend(version_issues)

            # Check tool.apworld section
            tool_apworld = pyproject_data.get("tool", {}).get("apworld", {})
            if not tool_apworld:
                warnings.append("No [tool.apworld] section found. Using defaults.")

            # Transform to manifest and validate
            try:
                manifest_data = transform_pyproject(pyproject)
                echo_info("  Transformed to manifest successfully")
            except ManifestTransformError as e:
                errors.append(f"Manifest transformation failed: {e}")

    # Validate manifest directly
    if manifest is not None:
        echo_info(f"Validating: {manifest}")

        try:
            with open(manifest) as f:
                manifest_data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON syntax: {e}")
            manifest_data = {}

        if manifest_data:
            # Derive package name from game
            game = manifest_data.get("game", "")
            if game:
                package_name = game.lower().replace(" ", "_").replace("-", "_")

    # Validate manifest schema
    if manifest_data:
        echo_info("  Validating manifest schema...")
        result = validate_manifest(manifest_data)

        if not result.valid:
            for error in result.errors:
                errors.append(f"Manifest error [{error.field}]: {error.message}")
        else:
            echo_info("  Manifest schema: valid")

            # Check version format in manifest
            world_version = manifest_data.get("world_version")
            if world_version:
                version_issues = _check_version_format(world_version)
                for issue in version_issues:
                    errors.append(f"world_version: {issue}")

            # Check AP version compatibility
            min_ap = manifest_data.get("minimum_ap_version")
            max_ap = manifest_data.get("maximum_ap_version")

            if min_ap and not is_valid_semver(min_ap):
                warnings.append(f"minimum_ap_version '{min_ap}' is not valid semver")

            if max_ap and not is_valid_semver(max_ap):
                warnings.append(f"maximum_ap_version '{max_ap}' is not valid semver")

            # Check required fields
            if not manifest_data.get("game"):
                errors.append("Missing required field: game")

            if manifest_data.get("version") is None:
                errors.append("Missing required field: version (schema version)")

            if manifest_data.get("compatible_version") is None:
                errors.append("Missing required field: compatible_version")

    # Validate package structure
    if check_structure and package_name:
        echo_info("  Checking package structure...")
        structure_issues = _validate_package_structure(project_dir, package_name)
        for issue in structure_issues:
            warnings.append(f"Structure: {issue}")

    # Report results
    echo_info("")

    if warnings:
        echo_warning(f"Warnings ({len(warnings)}):")
        for warning in warnings:
            echo_warning(f"  - {warning}")

    if errors:
        echo_error(f"Errors ({len(errors)}):")
        for error in errors:
            echo_error(f"  - {error}")

    # Determine exit status
    if errors:
        echo_error("\nValidation failed!")
        raise SystemExit(1)

    if warnings and strict:
        echo_error("\nValidation failed (strict mode)!")
        raise SystemExit(1)

    if warnings:
        echo_success("\nValidation passed with warnings.")
    else:
        echo_success("\nValidation passed!")
