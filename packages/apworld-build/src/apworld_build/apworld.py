# SPDX-License-Identifier: MIT
"""Binary distribution builder for APWorld packages.

This module creates .apworld binary distributions (ZIP archives) containing
compiled Python code, vendored dependencies, and the archipelago.json manifest.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from .filename import (
    PlatformTag,
    UNIVERSAL_TAG,
    build_apworld_filename,
    is_pure_python_tag,
)
from .sdist import DEFAULT_EXCLUDE_PATTERNS, _matches_any_pattern

if TYPE_CHECKING:
    from .config import BuildConfig


class ApworldError(Exception):
    """Raised when APWorld building fails."""

    pass


# File extensions that indicate native code
NATIVE_EXTENSIONS = {".so", ".dylib", ".dll", ".pyd"}


@dataclass
class ApworldResult:
    """Result of APWorld building.

    Attributes:
        path: Path to the created .apworld file
        filename: Name of the created file
        files_included: List of files included in the archive
        manifest: The generated archipelago.json manifest
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
    for root, _, files in os.walk(source_dir):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in NATIVE_EXTENSIONS:
                return True
    return False


def _collect_package_files(
    source_dir: Path,
    exclude_patterns: Optional[list[str]] = None,
) -> list[Path]:
    """Collect all files to include in the APWorld.

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
    vendored_dependencies: Optional[dict[str, str]] = None,
    is_pure_python: bool = True,
) -> dict[str, Any]:
    """Generate the archipelago.json manifest.

    Args:
        config: Build configuration
        vendored_dependencies: Dict mapping package names to versions
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

    return manifest


def build_apworld(
    config: "BuildConfig",
    output_dir: str | Path,
    source_dir: Optional[str | Path] = None,
    vendor_dir: Optional[str | Path] = None,
    platform_tag: Optional[PlatformTag] = None,
) -> ApworldResult:
    """Build an APWorld binary distribution (.apworld).

    Args:
        config: Build configuration with package metadata
        output_dir: Directory to write the .apworld file
        source_dir: Source directory (defaults to config.source_dir)
        vendor_dir: Directory containing vendored dependencies
        platform_tag: Platform tag (auto-detected if not provided)

    Returns:
        ApworldResult with information about the created archive

    Raises:
        ApworldError: If building fails
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    src_dir = Path(source_dir) if source_dir else config.source_dir
    if not src_dir.exists():
        raise ApworldError(f"Source directory does not exist: {src_dir}")

    # Detect if pure Python
    has_native = _detect_native_extensions(src_dir)
    if vendor_dir:
        vendor_path = Path(vendor_dir)
        if vendor_path.exists():
            has_native = has_native or _detect_native_extensions(vendor_path)

    is_pure_python = not has_native

    # Determine platform tag
    if platform_tag is None:
        platform_tag = UNIVERSAL_TAG if is_pure_python else _get_current_platform_tag()

    # Generate filename
    filename = build_apworld_filename(config.name, config.version, platform_tag)
    archive_path = output_path / filename

    # Collect vendored dependencies info
    vendored_deps: dict[str, str] = {}
    if vendor_dir:
        vendor_path = Path(vendor_dir)
        vendor_manifest = vendor_path / "vendor_manifest.json"
        if vendor_manifest.exists():
            with open(vendor_manifest) as f:
                vendor_data = json.load(f)
                for pkg_name, pkg_info in vendor_data.get("vendored_packages", {}).items():
                    vendored_deps[pkg_name] = pkg_info.get("version", "unknown")

    # Generate manifest
    manifest = _generate_manifest(config, vendored_deps, is_pure_python)

    # Build the archive
    files_included: list[str] = []

    # The APWorld structure is:
    # {package_name}/
    #   __init__.py
    #   ... (source files)
    #   _vendor/
    #     ... (vendored dependencies)
    #   archipelago.json

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        package_name = config.normalized_name

        # Add source files
        source_files = _collect_package_files(src_dir, config.exclude_patterns)
        for rel_path in source_files:
            full_path = src_dir / rel_path
            arcname = f"{package_name}/{rel_path}"
            zf.write(full_path, arcname)
            files_included.append(arcname)

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

        # Add manifest
        manifest_content = json.dumps(manifest, indent=2)
        manifest_arcname = f"{package_name}/archipelago.json"
        zf.writestr(manifest_arcname, manifest_content)
        files_included.append(manifest_arcname)

    return ApworldResult(
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


def build_apworld_with_vendoring(
    config: "BuildConfig",
    output_dir: str | Path,
    source_dir: Optional[str | Path] = None,
    platform_tag: Optional[PlatformTag] = None,
) -> ApworldResult:
    """Build an APWorld with automatic dependency vendoring.

    This function handles the complete build process:
    1. Vendors dependencies to a temporary directory
    2. Rewrites imports in source files
    3. Builds the APWorld archive

    Args:
        config: Build configuration with package metadata
        output_dir: Directory to write the .apworld file
        source_dir: Source directory (defaults to config.source_dir)
        platform_tag: Platform tag (auto-detected if not provided)

    Returns:
        ApworldResult with information about the created archive

    Raises:
        ApworldError: If building fails
    """
    from apworld_vendor import VendorConfig, vendor_dependencies, rewrite_imports

    src_dir = Path(source_dir) if source_dir else config.source_dir

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_dir = temp_path / "build"
        vendor_dir = temp_path / "vendor"

        # Copy source files to build directory
        shutil.copytree(src_dir, build_dir)

        # Vendor dependencies if any
        if config.dependencies:
            vendor_config = VendorConfig(
                package_name=config.normalized_name,
                dependencies=config.dependencies,
                exclude=config.vendor_exclude,
            )

            vendor_result = vendor_dependencies(vendor_config, vendor_dir)

            if vendor_result.errors:
                raise ApworldError(
                    f"Dependency vendoring failed: {'; '.join(vendor_result.errors)}"
                )

            # Rewrite imports if we vendored anything
            if vendor_result.packages:
                vendored_modules = vendor_result.get_vendored_module_names()
                rewrite_imports(
                    source_dir=build_dir,
                    output_dir=build_dir,
                    vendored_modules=vendored_modules,
                    config=vendor_config,
                )

        # Build the APWorld
        return build_apworld(
            config=config,
            output_dir=output_dir,
            source_dir=build_dir,
            vendor_dir=vendor_dir if config.dependencies else None,
            platform_tag=platform_tag,
        )
