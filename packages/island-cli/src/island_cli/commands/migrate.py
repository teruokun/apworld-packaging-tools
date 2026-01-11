# SPDX-License-Identifier: MIT
"""Migrate legacy archipelago.json and [tool.apworld] to island format."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import click
from island_manifest import (
    CURRENT_SCHEMA_VERSION,
    MANIFEST_DEFAULTS,
    MIN_COMPATIBLE_VERSION,
    validate_manifest,
)

from ..main import Context, echo_error, echo_info, echo_success, echo_warning, pass_context

PYPROJECT_TEMPLATE = """[build-system]
requires = ["hatchling", "island-build"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "{version}"
description = "{description}"
readme = "README.md"
license = {{text = "{license}"}}
requires-python = ">=3.10"
{authors_section}keywords = {keywords}
dependencies = []

[project.urls]
Homepage = "{homepage}"
Repository = "{repository}"

[project.entry-points.ap-island]
{entry_points_section}

[tool.island]
game = "{game}"
minimum_ap_version = "{minimum_ap_version}"
{maximum_ap_version_line}
[tool.island.vendor]
exclude = ["typing_extensions"]

[tool.hatch.build.targets.wheel]
packages = ["src/{package_name}"]
"""


def _normalize_name(name: str) -> str:
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


class WebWorldDetector:
    """Detects WebWorld subclasses in Python source files."""

    # Common base class names for Archipelago worlds
    WEBWORLD_BASE_CLASSES = {"WebWorld", "World"}

    def __init__(self) -> None:
        self.detected_classes: list[dict[str, str]] = []

    def scan_directory(self, source_dir: Path) -> list[dict[str, str]]:
        """Scan a directory for WebWorld subclasses.

        Args:
            source_dir: Directory to scan

        Returns:
            List of dicts with 'name', 'module', 'attr' keys
        """
        self.detected_classes = []

        for py_file in source_dir.rglob("*.py"):
            try:
                self._scan_file(py_file, source_dir)
            except SyntaxError:
                # Skip files with syntax errors
                continue

        return self.detected_classes

    def _scan_file(self, file_path: Path, source_dir: Path) -> None:
        """Scan a single Python file for WebWorld subclasses."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            return

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        # Get module path relative to source_dir
        rel_path = file_path.relative_to(source_dir)
        module_parts = list(rel_path.parts[:-1]) + [rel_path.stem]
        module_path = ".".join(module_parts)

        # Find class definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if self._is_webworld_subclass(node):
                    # Use the class name as the entry point name (lowercase)
                    entry_name = node.name.lower().replace("world", "")
                    if not entry_name:
                        entry_name = node.name.lower()

                    self.detected_classes.append(
                        {
                            "name": entry_name,
                            "module": module_path,
                            "attr": node.name,
                        }
                    )

    def _is_webworld_subclass(self, node: ast.ClassDef) -> bool:
        """Check if a class definition is a WebWorld subclass."""
        for base in node.bases:
            base_name = self._get_base_name(base)
            if base_name in self.WEBWORLD_BASE_CLASSES:
                return True
        return False

    def _get_base_name(self, node: ast.expr) -> str:
        """Extract the base class name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""


def detect_webworld_classes(source_dir: Path) -> list[dict[str, str]]:
    """Detect WebWorld subclasses in a source directory.

    Args:
        source_dir: Directory to scan for Python files

    Returns:
        List of detected WebWorld classes with module and attribute info
    """
    detector = WebWorldDetector()
    return detector.scan_directory(source_dir)


def _detect_legacy_apworld_config(pyproject_path: Path) -> dict[str, Any] | None:
    """Detect legacy [tool.apworld] configuration in pyproject.toml.

    Args:
        pyproject_path: Path to pyproject.toml

    Returns:
        The [tool.apworld] section if found, None otherwise
    """
    if not pyproject_path.exists():
        return None

    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
    except tomllib.TOMLDecodeError:
        return None

    return pyproject.get("tool", {}).get("apworld")


def _convert_apworld_to_island_config(
    pyproject_path: Path,
    entry_points: list[dict[str, str]] | None = None,
) -> str:
    """Convert [tool.apworld] to [tool.island] in pyproject.toml.

    Args:
        pyproject_path: Path to pyproject.toml
        entry_points: Optional list of detected entry points

    Returns:
        Updated pyproject.toml content as string
    """
    with open(pyproject_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace [tool.apworld] with [tool.island]
    content = re.sub(r"\[tool\.apworld\]", "[tool.island]", content)
    content = re.sub(r"\[tool\.apworld\.", "[tool.island.", content)

    # Add entry points section if not present and entry_points provided
    if entry_points and "[project.entry-points.ap-island]" not in content:
        # Find a good place to insert entry points (after [project.urls] or before [tool.island])
        entry_points_section = "\n[project.entry-points.ap-island]\n"
        for ep in entry_points:
            entry_points_section += f'{ep["name"]} = "{ep["module"]}:{ep["attr"]}"\n'

        # Try to insert after [project.urls] section
        urls_match = re.search(r"(\[project\.urls\][^\[]*)", content)
        if urls_match:
            insert_pos = urls_match.end()
            content = content[:insert_pos] + entry_points_section + content[insert_pos:]
        else:
            # Insert before [tool.island]
            tool_match = re.search(r"\[tool\.island\]", content)
            if tool_match:
                insert_pos = tool_match.start()
                content = content[:insert_pos] + entry_points_section + "\n" + content[insert_pos:]

    return content


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
            if isinstance(default_value, list | dict):
                migrated[key] = default_value.copy()
            else:
                migrated[key] = default_value

    return migrated


def _generate_pyproject(
    manifest: dict[str, Any],
    package_name: str,
    entry_points: list[dict[str, str]] | None = None,
) -> str:
    """Generate pyproject.toml content from a manifest.

    Args:
        manifest: Migrated manifest
        package_name: Normalized package name
        entry_points: Optional list of detected entry points

    Returns:
        pyproject.toml content as string
    """
    game = manifest.get("game", "Unknown Game")
    version = manifest.get("world_version", "0.1.0")
    description = manifest.get("description", f"Archipelago randomizer implementation for {game}")

    # License (default to MIT like init template)
    license_text = manifest.get("license", "MIT")

    # Authors section
    authors = manifest.get("authors", [])
    if authors:
        authors_lines = []
        for author in authors:
            authors_lines.append(f'    {{name = "{author}"}}')
        authors_section = "authors = [\n" + ",\n".join(authors_lines) + "\n]\n"
    else:
        authors_section = 'authors = [\n    {name = "Your Name"}\n]\n'

    # Keywords (include archipelago and randomizer like init template)
    keywords = manifest.get("keywords", [])
    game_lower = game.lower().replace(" ", "-")
    default_keywords = [game_lower, "archipelago", "randomizer"]
    # Merge with existing keywords, avoiding duplicates
    merged_keywords = list(dict.fromkeys(default_keywords + keywords))
    keywords_str = json.dumps(merged_keywords)

    # URLs (always include both like init template)
    homepage = manifest.get("homepage", "https://github.com/ArchipelagoMW/Archipelago")
    repository = manifest.get("repository", "https://github.com/ArchipelagoMW/Archipelago")

    # AP version (default minimum like init template)
    minimum_ap_version = manifest.get("minimum_ap_version", "0.5.0")
    maximum_ap_version = manifest.get("maximum_ap_version")
    maximum_ap_version_line = (
        f'maximum_ap_version = "{maximum_ap_version}"\n' if maximum_ap_version else ""
    )

    # Entry points section
    if entry_points:
        entry_points_lines = []
        for ep in entry_points:
            entry_points_lines.append(f'{ep["name"]} = "{ep["module"]}:{ep["attr"]}"')
        entry_points_section = "\n".join(entry_points_lines)
    else:
        # Default placeholder entry point
        entry_points_section = (
            f'{package_name} = "{package_name}.world:{package_name.title().replace("_", "")}World"'
        )

    return PYPROJECT_TEMPLATE.format(
        name=package_name.replace("_", "-"),
        package_name=package_name,
        version=version,
        description=description,
        license=license_text,
        authors_section=authors_section,
        keywords=keywords_str,
        homepage=homepage,
        repository=repository,
        game=game,
        minimum_ap_version=minimum_ap_version,
        maximum_ap_version_line=maximum_ap_version_line,
        entry_points_section=entry_points_section,
    )


class MigrationValidationError(Exception):
    """Raised when migration validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Migration validation failed: {'; '.join(errors)}")


def validate_migrated_package(
    project_dir: Path,
    package_name: str,
) -> list[str]:
    """Validate that a migrated package meets island format requirements.

    Args:
        project_dir: Project directory containing pyproject.toml
        package_name: Normalized package name

    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []

    # Check pyproject.toml exists
    pyproject_path = project_dir / "pyproject.toml"
    if not pyproject_path.exists():
        errors.append("pyproject.toml not found")
        return errors

    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        errors.append(f"Invalid TOML syntax: {e}")
        return errors

    # Check required [project] fields
    project = pyproject.get("project", {})
    if not project.get("name"):
        errors.append("Missing required field: [project].name")
    if not project.get("version"):
        errors.append("Missing required field: [project].version")

    # Check [tool.island] section exists
    tool_island = pyproject.get("tool", {}).get("island", {})
    if not tool_island:
        errors.append("Missing [tool.island] section")

    # Check for legacy [tool.apworld] section
    tool_apworld = pyproject.get("tool", {}).get("apworld")
    if tool_apworld:
        errors.append("Legacy [tool.apworld] section found - should be [tool.island]")

    # Check for ap-island entry points
    entry_points = project.get("entry-points", {})
    ap_island_eps = entry_points.get("ap-island", {})
    if not ap_island_eps:
        errors.append("Missing required [project.entry-points.ap-island] entry points")

    # Check source directory exists
    src_candidates = [
        project_dir / "src" / package_name,
        project_dir / package_name,
    ]
    source_found = False
    for candidate in src_candidates:
        if candidate.exists():
            source_found = True
            break

    if not source_found:
        errors.append(f"Source directory not found: src/{package_name}/ or {package_name}/")

    return errors


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
    "--from-apworld",
    is_flag=True,
    help="Migrate from legacy [tool.apworld] configuration to [tool.island].",
)
@click.option(
    "--detect-entry-points",
    is_flag=True,
    help="Automatically detect WebWorld classes and generate entry points.",
)
@click.option(
    "--source-dir",
    "-s",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Source directory for WebWorld detection (defaults to auto-detection).",
)
@click.option(
    "--validate",
    "validate_result",
    is_flag=True,
    help="Validate the migrated package meets island format requirements.",
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
    input_path: Path | None,
    output_path: Path | None,
    generate_pyproject: bool,
    pyproject_output: Path | None,
    from_apworld: bool,
    detect_entry_points: bool,
    source_dir: Path | None,
    validate_result: bool,
    dry_run: bool,
    force: bool,
) -> None:
    """Migrate legacy formats to island format.

    Supports two migration modes:

    1. Legacy archipelago.json migration (default):
       Reads a legacy archipelago.json file and updates it to the modern schema.

    2. [tool.apworld] to [tool.island] migration (--from-apworld):
       Converts existing pyproject.toml from [tool.apworld] to [tool.island].

    Both modes can automatically detect WebWorld classes and generate entry points.

    \b
    Examples:
        island migrate                          # Migrate archipelago.json
        island migrate --generate-pyproject     # Also create pyproject.toml
        island migrate --from-apworld           # Convert [tool.apworld] to [tool.island]
        island migrate --detect-entry-points    # Auto-detect WebWorld classes
        island migrate --validate               # Validate after migration
        island migrate --dry-run                # Preview changes
    """
    project_dir = ctx.project_dir or Path.cwd()

    # Detect entry points if requested
    detected_entry_points: list[dict[str, str]] = []
    if detect_entry_points:
        # Find source directory
        if source_dir is None:
            # Try common locations
            for candidate in [
                project_dir / "src",
                project_dir,
            ]:
                if candidate.exists() and any(candidate.glob("**/*.py")):
                    source_dir = candidate
                    break

        if source_dir:
            echo_info(f"Scanning for WebWorld classes in: {source_dir}")
            detected_entry_points = detect_webworld_classes(source_dir)
            if detected_entry_points:
                echo_success(f"  Detected {len(detected_entry_points)} WebWorld class(es):")
                for ep in detected_entry_points:
                    echo_info(f"    {ep['name']} = {ep['module']}:{ep['attr']}")
            else:
                echo_warning("  No WebWorld classes detected")
        else:
            echo_warning("Could not find source directory for WebWorld detection")

    # Handle --from-apworld mode
    if from_apworld:
        pyproject_path = project_dir / "pyproject.toml"
        if not pyproject_path.exists():
            echo_error(f"pyproject.toml not found: {pyproject_path}")
            raise SystemExit(1)

        # Check for legacy [tool.apworld] section
        legacy_config = _detect_legacy_apworld_config(pyproject_path)
        if not legacy_config:
            echo_warning("No [tool.apworld] section found in pyproject.toml")
            echo_info("Nothing to migrate.")
            return

        echo_info(f"Found legacy [tool.apworld] configuration in: {pyproject_path}")
        echo_info("Converting to [tool.island]...")

        # Convert configuration
        updated_content = _convert_apworld_to_island_config(
            pyproject_path,
            entry_points=detected_entry_points if detect_entry_points else None,
        )

        if ctx.verbose or dry_run:
            echo_info("\nUpdated pyproject.toml:")
            echo_info(updated_content)

        if dry_run:
            echo_warning("\nDry run - no files written.")
            echo_info(f"Would update: {pyproject_path}")
        else:
            # Backup original
            if not force:
                backup_path = pyproject_path.with_suffix(".toml.bak")
                if backup_path.exists():
                    echo_error(f"Backup file exists: {backup_path}")
                    echo_info("Use --force to overwrite.")
                    raise SystemExit(1)
                import shutil

                shutil.copy(pyproject_path, backup_path)
                echo_info(f"Backed up original to: {backup_path}")

            with open(pyproject_path, "w") as f:
                f.write(updated_content)
            echo_success(f"Updated: {pyproject_path}")

        # Validate if requested
        if validate_result:
            echo_info("\nValidating migrated package...")
            # Get package name from pyproject
            try:
                with open(pyproject_path, "rb") as f:
                    pyproject = tomllib.load(f)
                package_name = pyproject.get("project", {}).get("name", "").replace("-", "_")
            except Exception:
                package_name = ""

            if package_name:
                validation_errors = validate_migrated_package(project_dir, package_name)
                if validation_errors:
                    echo_error("Validation failed:")
                    for error in validation_errors:
                        echo_error(f"  - {error}")
                    raise SystemExit(1)
                else:
                    echo_success("Validation passed!")

        echo_success("\nMigration complete!")
        echo_info("\nNext steps:")
        echo_info("  1. Review the updated pyproject.toml")
        echo_info("  2. Run 'island validate' to verify")
        echo_info("  3. Run 'island build' to create distributions")
        return

    # Handle legacy archipelago.json migration (original behavior)
    if input_path is None:
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
        raise SystemExit(1) from e

    # Check if already modern
    if legacy_manifest.get("version") == CURRENT_SCHEMA_VERSION:
        echo_warning("Manifest already uses modern schema version.")
        if not force:
            echo_info("Use --force to re-migrate anyway.")
            return

    # Migrate manifest
    echo_info("Migrating to modern schema...")
    migrated = _migrate_manifest(legacy_manifest)

    # Add entry points to manifest if detected
    if detected_entry_points:
        migrated["entry_points"] = {
            "ap-island": {
                ep["name"]: f"{ep['module']}:{ep['attr']}" for ep in detected_entry_points
            }
        }

    # Validate migrated manifest
    validation_result = validate_manifest(migrated)
    if not validation_result.valid:
        echo_error("Migration produced invalid manifest:")
        for error in validation_result.errors:
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
    pyproject_content: str | None = None
    if generate_pyproject:
        game = migrated.get("game", "Unknown")
        package_name = _normalize_name(game)
        pyproject_content = _generate_pyproject(
            migrated,
            package_name,
            entry_points=detected_entry_points if detected_entry_points else None,
        )

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

    # Validate if requested
    if validate_result and generate_pyproject and pyproject_output:
        echo_info("\nValidating migrated package...")
        game = migrated.get("game", "Unknown")
        package_name = _normalize_name(game)
        validation_errors = validate_migrated_package(pyproject_output.parent, package_name)
        if validation_errors:
            echo_error("Validation failed:")
            for error in validation_errors:
                echo_error(f"  - {error}")
            raise SystemExit(1)
        else:
            echo_success("Validation passed!")

    echo_success("\nMigration complete!")

    if generate_pyproject:
        echo_info("\nNext steps:")
        echo_info("  1. Review and customize pyproject.toml")
        echo_info("  2. Run 'island validate' to verify")
        echo_info("  3. Run 'island build' to create distributions")
