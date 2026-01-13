# SPDX-License-Identifier: MIT
"""Binary distribution builder for Island packages.

This module creates .island binary distributions (ZIP archives) containing
compiled Python code, vendored dependencies, and the island.json manifest.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from .filename import (
    PlatformTag,
    UNIVERSAL_TAG,
    build_island_filename,
)
from .sdist import DEFAULT_EXCLUDE_PATTERNS, _matches_any_pattern
from .wheel import (
    EntryPointsFile,
    PackageMetadata,
    RecordFile,
    WheelMetadata,
    get_dist_info_name,
)

if TYPE_CHECKING:
    from .config import BuildConfig


class IslandError(Exception):
    """Raised when Island building fails."""

    pass


class MissingEntryPointError(IslandError):
    """Raised when required ap-island entry points are missing.

    Island packages must declare at least one entry point of type `ap-island`
    in the `[project.entry-points.ap-island]` section of pyproject.toml.

    Example:
        [project.entry-points.ap-island]
        my_game = "my_game.world:MyGameWorld"
    """

    def __init__(self, message: str | None = None):
        if message is None:
            message = (
                "Island packages must declare at least one [project.entry-points.ap-island] "
                "entry point. Add an entry point that references your WebWorld implementation."
            )
        super().__init__(message)


class InvalidEntryPointError(IslandError):
    """Raised when an entry point has invalid format.

    Entry points must follow the format: `module.path:attribute`
    where module.path is a valid Python module path and attribute
    is a valid Python identifier.
    """

    def __init__(self, name: str, value: str, reason: str):
        message = f"Invalid entry point '{name} = {value}': {reason}"
        super().__init__(message)
        self.name = name
        self.value = value
        self.reason = reason


# Regex pattern for validating entry point format
# Format: module.path:attribute
ENTRY_POINT_PATTERN = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*:[a-zA-Z_][a-zA-Z0-9_]*$"
)

# File extensions that indicate native code
NATIVE_EXTENSIONS = {".so", ".dylib", ".dll", ".pyd"}


def validate_entry_point_format(name: str, value: str) -> None:
    """Validate that an entry point has the correct format.

    Args:
        name: Entry point name
        value: Entry point value (e.g., "my_game.world:MyGameWorld")

    Raises:
        InvalidEntryPointError: If the format is invalid
    """
    if not value:
        raise InvalidEntryPointError(name, value, "Entry point value cannot be empty")

    if ":" not in value:
        raise InvalidEntryPointError(
            name, value, "Entry point must contain ':' separator (format: module.path:attribute)"
        )

    if not ENTRY_POINT_PATTERN.match(value):
        raise InvalidEntryPointError(
            name,
            value,
            "Entry point must match format 'module.path:attribute' with valid Python identifiers",
        )


def validate_entry_points(entry_points: dict[str, dict[str, str]] | None) -> None:
    """Validate that entry points meet Island package requirements.

    Island packages must have at least one ap-island entry point.
    All entry points must have valid format.

    Args:
        entry_points: Dictionary of entry point groups to entry point dicts

    Raises:
        MissingEntryPointError: If no ap-island entry points exist
        InvalidEntryPointError: If any entry point has invalid format
    """
    if not entry_points:
        raise MissingEntryPointError()

    ap_island_eps = entry_points.get("ap-island", {})
    if not ap_island_eps:
        raise MissingEntryPointError()

    # Validate each entry point format
    for name, value in ap_island_eps.items():
        validate_entry_point_format(name, value)


def extract_entry_points_from_pyproject(pyproject: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Extract entry points from a pyproject.toml dictionary.

    Args:
        pyproject: Parsed pyproject.toml dictionary

    Returns:
        Dictionary mapping group names to entry point dictionaries
    """
    return pyproject.get("project", {}).get("entry-points", {})


@dataclass
class IslandResult:
    """Result of Island building.

    Attributes:
        path: Path to the created .island file
        filename: Name of the created file
        files_included: List of files included in the archive
        manifest: The generated island.json manifest
        size: Size of the archive in bytes
        is_pure_python: Whether the package is pure Python
        platform_tag: Platform tag used for the filename
    """

    path: Path
    filename: str
    files_included: list[str]
    manifest: dict[str, Any]
    size: int
    is_pure_python: bool
    platform_tag: PlatformTag


def _detect_native_extensions(source_dir: Path) -> bool:
    """Detect if a directory contains native extensions.

    Args:
        source_dir: Directory to scan

    Returns:
        True if native extensions are found
    """
    for _root, _, files in os.walk(source_dir):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in NATIVE_EXTENSIONS:
                return True
    return False


def _collect_package_files(
    source_dir: Path,
    exclude_patterns: Optional[list[str]] = None,
) -> list[Path]:
    """Collect all files to include in the Island.

    Args:
        source_dir: Root directory to collect files from
        exclude_patterns: Glob patterns for files to exclude

    Returns:
        List of paths to include (relative to source_dir)
    """
    exclude_patterns = exclude_patterns or DEFAULT_EXCLUDE_PATTERNS.copy()
    collected: list[Path] = []

    for root, dirs, files in os.walk(source_dir):
        # Filter directories
        dirs[:] = [
            d
            for d in dirs
            if not _matches_any_pattern(d, exclude_patterns)
            and not _matches_any_pattern(os.path.join(root, d), exclude_patterns)
        ]

        for filename in files:
            full_path = Path(root) / filename
            rel_path = full_path.relative_to(source_dir)
            rel_path_str = str(rel_path)

            # Skip excluded files
            if _matches_any_pattern(rel_path_str, exclude_patterns):
                continue
            if _matches_any_pattern(filename, exclude_patterns):
                continue

            collected.append(rel_path)

    return sorted(collected)


def _generate_manifest(
    config: "BuildConfig",
    entry_points: Optional[dict[str, dict[str, str]]] = None,
    vendored_dependencies: Optional[dict[str, Any]] = None,
    is_pure_python: bool = True,
) -> dict[str, Any]:
    """Generate the island.json manifest.

    Args:
        config: Build configuration
        entry_points: Entry points dict (group -> {name -> value})
        vendored_dependencies: Dict with vendored package info including platform tags.
            Can be either:
            - Simple format: {package_name: version_string}
            - Enhanced format: {package_name: {version, is_pure_python, platform_tags, ...}}
        is_pure_python: Whether the package is pure Python

    Returns:
        Manifest dictionary
    """
    manifest: dict[str, Any] = {
        "game": config.game_name,
        "version": config.schema_version,
        "compatible_version": config.compatible_version,
    }

    if config.version:
        manifest["world_version"] = config.version

    if config.minimum_ap_version:
        manifest["minimum_ap_version"] = config.minimum_ap_version

    if config.maximum_ap_version:
        manifest["maximum_ap_version"] = config.maximum_ap_version

    if config.authors:
        manifest["authors"] = config.authors

    if config.description:
        manifest["description"] = config.description

    if config.license:
        manifest["license"] = config.license

    if config.homepage:
        manifest["homepage"] = config.homepage

    if config.repository:
        manifest["repository"] = config.repository

    if config.keywords:
        manifest["keywords"] = config.keywords

    if config.platforms:
        manifest["platforms"] = config.platforms

    manifest["pure_python"] = is_pure_python

    if vendored_dependencies:
        manifest["vendored_dependencies"] = vendored_dependencies

    # Add entry points to manifest (required field for island format)
    if entry_points:
        manifest["entry_points"] = entry_points

    return manifest


def build_island(
    config: "BuildConfig",
    output_dir: str | Path,
    source_dir: str | Path | None = None,
    vendor_dir: str | Path | None = None,
    platform_tag: PlatformTag | None = None,
    entry_points: dict[str, dict[str, str]] | None = None,
    vendored_dependencies_info: dict[str, Any] | None = None,
) -> IslandResult:
    """Build an Island binary distribution (.island).

    Note: This function does NOT validate entry points. Use validate_entry_points()
    separately to enforce the Island format requirement for ap-island entry points.
    This separation allows for flexibility in testing and backward compatibility.

    Args:
        config: Build configuration with package metadata
        output_dir: Directory to write the .island file
        source_dir: Source directory (defaults to config.source_dir)
        vendor_dir: Directory containing vendored dependencies
        platform_tag: Platform tag (auto-detected if not provided)
        entry_points: Entry points dict (group -> {name -> value})
        vendored_dependencies_info: Enhanced vendored dependency info with platform tags.
            If provided, this takes precedence over reading from vendor_manifest.json.
            Format: {package_name: {version, is_pure_python, platform_tags, ...}}

    Returns:
        IslandResult with information about the created archive

    Raises:
        IslandError: If building fails
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    src_dir = Path(source_dir) if source_dir else config.source_dir
    if not src_dir.exists():
        raise IslandError(f"Source directory does not exist: {src_dir}")

    # Detect if pure Python from source and vendor directories
    has_native = _detect_native_extensions(src_dir)
    if vendor_dir:
        vendor_path = Path(vendor_dir)
        if vendor_path.exists():
            has_native = has_native or _detect_native_extensions(vendor_path)

    is_pure_python = not has_native

    # Also check vendored dependencies info for platform-specific packages
    if vendored_dependencies_info is not None:
        for pkg_info in vendored_dependencies_info.values():
            if isinstance(pkg_info, dict) and not pkg_info.get("is_pure_python", True):
                is_pure_python = False
                break

    # Determine platform tag
    if platform_tag is None:
        platform_tag = UNIVERSAL_TAG if is_pure_python else _get_current_platform_tag()

    # Generate filename
    filename = build_island_filename(config.name, config.version, platform_tag)
    archive_path = output_path / filename

    # Collect vendored dependencies info
    vendored_deps: dict[str, Any] = {}
    if vendored_dependencies_info is not None:
        # Use provided enhanced info
        vendored_deps = vendored_dependencies_info
    elif vendor_dir:
        # Fall back to reading from vendor_manifest.json
        vendor_path = Path(vendor_dir)
        vendor_manifest = vendor_path / "vendor_manifest.json"
        if vendor_manifest.exists():
            with open(vendor_manifest) as f:
                vendor_data = json.load(f)
                # Use enhanced format from vendor manifest
                vendored_deps = vendor_data.get("vendored_packages", {})

    # Generate manifest (includes entry_points if provided)
    manifest = _generate_manifest(config, entry_points, vendored_deps, is_pure_python)

    # Build the archive
    files_included: list[str] = []

    # Get dist-info directory name
    dist_info_name = get_dist_info_name(config.name, config.version)
    package_name = config.normalized_name

    # Create RECORD tracker
    record = RecordFile(record_path=f"{dist_info_name}/RECORD")

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add source files
        source_files = _collect_package_files(src_dir, config.exclude_patterns)
        for rel_path in source_files:
            full_path = src_dir / rel_path
            arcname = f"{package_name}/{rel_path}"
            zf.write(full_path, arcname)
            files_included.append(arcname)
            record.add_file(arcname, full_path)

        # Add vendored dependencies
        if vendor_dir:
            vendor_path = Path(vendor_dir)
            if vendor_path.exists():
                vendor_files = _collect_package_files(vendor_path)
                for rel_path in vendor_files:
                    full_path = vendor_path / rel_path
                    arcname = f"{package_name}/_vendor/{rel_path}"
                    zf.write(full_path, arcname)
                    files_included.append(arcname)
                    record.add_file(arcname, full_path)

        # Generate and add WHEEL file
        wheel_meta = WheelMetadata.from_platform_tag(platform_tag)
        wheel_content = wheel_meta.to_string().encode("utf-8")
        wheel_arcname = f"{dist_info_name}/WHEEL"
        zf.writestr(wheel_arcname, wheel_content)
        files_included.append(wheel_arcname)
        record.add_content(wheel_arcname, wheel_content)

        # Generate and add METADATA file
        pkg_meta = PackageMetadata.from_build_config(config)
        metadata_content = pkg_meta.to_string().encode("utf-8")
        metadata_arcname = f"{dist_info_name}/METADATA"
        zf.writestr(metadata_arcname, metadata_content)
        files_included.append(metadata_arcname)
        record.add_content(metadata_arcname, metadata_content)

        # Generate and add entry_points.txt if entry points provided
        if entry_points:
            ep_file = EntryPointsFile()
            for group, entries in entry_points.items():
                for name, value in entries.items():
                    ep_file.add_entry_point(group, name, value)
            ep_content = ep_file.to_string().encode("utf-8")
            if ep_content:  # Only add if there are entry points
                ep_arcname = f"{dist_info_name}/entry_points.txt"
                zf.writestr(ep_arcname, ep_content)
                files_included.append(ep_arcname)
                record.add_content(ep_arcname, ep_content)

        # Add island.json manifest to dist-info
        manifest_content = json.dumps(manifest, indent=2).encode("utf-8")
        manifest_arcname = f"{dist_info_name}/island.json"
        zf.writestr(manifest_arcname, manifest_content)
        files_included.append(manifest_arcname)
        record.add_content(manifest_arcname, manifest_content)

        # Generate and add RECORD file (must be last)
        record_content = record.to_string().encode("utf-8")
        record_arcname = f"{dist_info_name}/RECORD"
        zf.writestr(record_arcname, record_content)
        files_included.append(record_arcname)

    return IslandResult(
        path=archive_path,
        filename=filename,
        files_included=files_included,
        manifest=manifest,
        size=archive_path.stat().st_size,
        is_pure_python=is_pure_python,
        platform_tag=platform_tag,
    )


def _get_current_platform_tag() -> PlatformTag:
    """Get the platform tag for the current system.

    Returns:
        PlatformTag for the current platform
    """
    import platform
    import sys

    # Get Python version
    py_version = f"cp{sys.version_info.major}{sys.version_info.minor}"

    # Get platform
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        if machine in ("amd64", "x86_64"):
            plat = "win_amd64"
        elif machine in ("arm64", "aarch64"):
            plat = "win_arm64"
        else:
            plat = f"win_{machine}"
    elif system == "darwin":
        # macOS
        if machine in ("arm64", "aarch64"):
            plat = "macosx_11_0_arm64"
        else:
            plat = "macosx_11_0_x86_64"
    elif system == "linux":
        if machine in ("x86_64", "amd64"):
            plat = "manylinux_2_17_x86_64"
        elif machine in ("aarch64", "arm64"):
            plat = "manylinux_2_17_aarch64"
        else:
            plat = f"linux_{machine}"
    else:
        plat = f"{system}_{machine}"

    return PlatformTag(python=py_version, abi=py_version, platform=plat)


def build_island_with_vendoring(
    config: "BuildConfig",
    output_dir: str | Path,
    source_dir: str | Path | None = None,
    platform_tag: PlatformTag | None = None,
    entry_points: dict[str, dict[str, str]] | None = None,
) -> IslandResult:
    """Build an Island with automatic dependency vendoring.

    This function handles the complete build process:
    1. Vendors dependencies to a temporary directory
    2. Rewrites imports in source files
    3. Builds the Island archive with platform tag from vendored dependencies

    Note: This function does NOT validate entry points. Use validate_entry_points()
    separately to enforce the Island format requirement for ap-island entry points.

    Args:
        config: Build configuration with package metadata
        output_dir: Directory to write the .island file
        source_dir: Source directory (defaults to config.source_dir)
        platform_tag: Platform tag (auto-detected from vendored dependencies if not provided)
        entry_points: Entry points dict (group -> {name -> value})

    Returns:
        IslandResult with information about the created archive

    Raises:
        IslandError: If building fails
    """
    from island_vendor import VendorConfig, rewrite_imports, vendor_dependencies

    src_dir = Path(source_dir) if source_dir else config.source_dir

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_dir = temp_path / "build"
        vendor_dir = temp_path / "vendor"

        # Copy source files to build directory
        shutil.copytree(src_dir, build_dir)

        # Track vendor result for platform tag propagation
        vendor_result = None

        # Vendor dependencies if any
        if config.dependencies:
            vendor_config = VendorConfig(
                package_name=config.normalized_name,
                dependencies=config.dependencies,
                exclude=config.vendor_exclude,
            )

            vendor_result = vendor_dependencies(vendor_config, vendor_dir)

            if vendor_result.errors:
                raise IslandError(f"Dependency vendoring failed: {'; '.join(vendor_result.errors)}")

            # Rewrite imports if we vendored anything
            if vendor_result.packages:
                vendored_modules = vendor_result.get_vendored_module_names()
                rewrite_imports(
                    source_dir=build_dir,
                    output_dir=build_dir,
                    vendored_modules=vendored_modules,
                    config=vendor_config,
                )

        # Determine platform tag from vendored dependencies if not explicitly provided
        effective_platform_tag = platform_tag
        if effective_platform_tag is None and vendor_result is not None:
            # Get platform tag from VendorResult
            if vendor_result.platform_tag is not None:
                # Convert island_vendor.PlatformTag to island_build.PlatformTag
                vendor_tag = vendor_result.platform_tag
                effective_platform_tag = PlatformTag(
                    python=vendor_tag.python_tag,
                    abi=vendor_tag.abi_tag,
                    platform=vendor_tag.platform_tag,
                )

        # Extract enhanced vendored dependencies info from VendorResult
        vendored_dependencies_info: dict[str, Any] | None = None
        if vendor_result is not None and vendor_result.dependency_graph is not None:
            vendored_dependencies_info = {}
            for pkg_name, resolved_pkg in vendor_result.dependency_graph.packages.items():
                vendored_dependencies_info[pkg_name] = {
                    "version": resolved_pkg.version,
                    "is_pure_python": resolved_pkg.is_pure_python,
                    "platform_tags": resolved_pkg.platform_tags,
                    "direct_dependencies": resolved_pkg.requires,
                }
            # Add module info from VendoredPackage
            for pkg in vendor_result.packages:
                if pkg.name in vendored_dependencies_info:
                    vendored_dependencies_info[pkg.name]["modules"] = pkg.top_level_modules

        # Build the Island
        return build_island(
            config=config,
            output_dir=output_dir,
            source_dir=build_dir,
            vendor_dir=vendor_dir if config.dependencies else None,
            platform_tag=effective_platform_tag,
            entry_points=entry_points,
            vendored_dependencies_info=vendored_dependencies_info,
        )
