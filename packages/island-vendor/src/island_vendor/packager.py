# SPDX-License-Identifier: MIT
"""Dependency vendoring packager for Island packages.

This module downloads and extracts Python dependencies into a vendor directory,
preparing them for inclusion in Island packages.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import VendorConfig

from .config import VendoredPackage, VendorResult
from .resolver import DependencyResolver, DependencyResolverError


class DependencyDownloadError(Exception):
    """Raised when dependency download fails."""

    pass


class VendorPackageError(Exception):
    """Raised when vendoring a package fails."""

    pass


def _normalize_package_name(name: str) -> str:
    """Normalize a package name for comparison.

    PEP 503: Package names are case-insensitive and treat
    hyphens, underscores, and periods as equivalent.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_requirement(requirement: str) -> str:
    """Extract package name from a requirement string.

    Args:
        requirement: Pip requirement string (e.g., "pyyaml>=6.0", "requests[security]")

    Returns:
        Normalized package name
    """
    # Remove extras, version specifiers, and environment markers
    # Pattern matches: name[extras]>=version;marker
    match = re.match(r"^([a-zA-Z0-9][-a-zA-Z0-9._]*)", requirement)
    if match:
        return _normalize_package_name(match.group(1))
    return _normalize_package_name(requirement)


def _get_top_level_modules(package_dir: Path) -> list[str]:
    """Discover top-level modules in a package directory.

    This looks for:
    - Directories with __init__.py (packages)
    - .py files (modules)
    - top_level.txt from wheel metadata

    Args:
        package_dir: Directory containing the extracted package

    Returns:
        List of top-level module names
    """
    modules: list[str] = []

    # First, try to find top_level.txt in .dist-info
    for dist_info in package_dir.glob("*.dist-info"):
        top_level_file = dist_info / "top_level.txt"
        if top_level_file.exists():
            content = top_level_file.read_text(encoding="utf-8")
            modules.extend(line.strip() for line in content.splitlines() if line.strip())
            return modules

    # Fall back to directory inspection
    for item in package_dir.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            # It's a package
            modules.append(item.name)
        elif item.is_file() and item.suffix == ".py" and item.stem != "__init__":
            # It's a module
            modules.append(item.stem)

    return modules


def _get_package_version(package_dir: Path, package_name: str) -> str:
    """Get the version of an installed package.

    Args:
        package_dir: Directory containing the extracted package
        package_name: Name of the package

    Returns:
        Version string, or "unknown" if not found
    """
    normalized = _normalize_package_name(package_name)

    # Look for .dist-info directory
    for dist_info in package_dir.glob("*.dist-info"):
        # Check if this dist-info matches our package
        dist_name = dist_info.name.rsplit("-", 1)[0]  # Remove version suffix
        if _normalize_package_name(dist_name) == normalized:
            metadata_file = dist_info / "METADATA"
            if metadata_file.exists():
                content = metadata_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.startswith("Version:"):
                        return line.split(":", 1)[1].strip()

    return "unknown"


def download_dependencies(
    requirements: list[str],
    target_dir: Path,
    python_executable: str | None = None,
) -> dict[str, Path]:
    """Download dependencies using pip.

    Args:
        requirements: List of pip requirement strings
        target_dir: Directory to download packages to
        python_executable: Python executable to use (default: current interpreter)

    Returns:
        Dictionary mapping package names to their extracted paths

    Raises:
        DependencyDownloadError: If download fails
    """
    if not requirements:
        return {}

    python = python_executable or sys.executable
    target_dir.mkdir(parents=True, exist_ok=True)

    # Use pip to download and install to target directory
    cmd = [
        python,
        "-m",
        "pip",
        "install",
        "--target",
        str(target_dir),
        "--no-deps",  # We handle dependencies ourselves
        "--no-compile",  # Don't compile .pyc files
        "--quiet",
    ]
    cmd.extend(requirements)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise DependencyDownloadError(f"pip install failed:\n{result.stderr}\n{result.stdout}")
    except FileNotFoundError:
        raise DependencyDownloadError(f"Python executable not found: {python}") from None
    except Exception as e:
        raise DependencyDownloadError(f"Failed to run pip: {e}") from e

    # Map package names to their paths
    packages: dict[str, Path] = {}
    for req in requirements:
        pkg_name = _parse_requirement(req)
        packages[pkg_name] = target_dir

    return packages


def vendor_dependencies(
    config: VendorConfig,
    target_dir: str | Path,
    python_executable: str | None = None,
) -> VendorResult:
    """Vendor dependencies into a target directory.

    This function:
    1. Uses DependencyResolver to resolve all transitive dependencies
    2. Downloads and extracts them to the target directory
    3. Tracks which packages were vendored with platform information

    Args:
        config: Vendor configuration
        target_dir: Directory to vendor packages into
        python_executable: Python executable to use for pip

    Returns:
        VendorResult with information about vendored packages
    """
    result = VendorResult(target_dir=Path(target_dir))

    if not config.dependencies:
        return result

    # Create the resolver with exclusion rules
    resolver = DependencyResolver(
        exclude_packages=set(config.exclude),
        core_ap_modules=config.core_ap_modules,
    )

    # Resolve all dependencies including transitive ones
    try:
        dependency_graph = resolver.resolve_and_filter(
            config.dependencies,
            python_executable,
        )
    except DependencyResolverError as e:
        result.errors.append(str(e))
        return result

    # If no packages to vendor after filtering, return early
    if not dependency_graph.packages:
        return result

    # Store the dependency graph in the result
    result.dependency_graph = dependency_graph

    # Create a temporary directory for downloading
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Download all resolved packages
        packages_to_download = [
            f"{pkg.name}=={pkg.version}" for pkg in dependency_graph.packages.values()
        ]

        try:
            download_dependencies(
                packages_to_download,
                temp_path,
                python_executable,
            )
        except DependencyDownloadError as e:
            result.errors.append(str(e))
            return result

        # Process each downloaded package
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        for pkg_name, resolved_pkg in dependency_graph.packages.items():
            try:
                # Get package info
                version = resolved_pkg.version
                top_level = _get_top_level_modules(temp_path)

                # Filter to modules that match this package
                pkg_modules = [
                    m
                    for m in top_level
                    if (temp_path / m).exists() or (temp_path / f"{m}.py").exists()
                ]

                # Copy package files to target
                for module_name in pkg_modules:
                    src_dir = temp_path / module_name
                    src_file = temp_path / f"{module_name}.py"
                    dst_dir = target_path / module_name
                    dst_file = target_path / f"{module_name}.py"

                    if src_dir.is_dir():
                        if dst_dir.exists():
                            shutil.rmtree(dst_dir)
                        shutil.copytree(src_dir, dst_dir)
                    elif src_file.is_file():
                        shutil.copy2(src_file, dst_file)

                vendored_pkg = VendoredPackage(
                    name=pkg_name,
                    version=version,
                    source_path=target_path,
                    top_level_modules=pkg_modules,
                )
                result.packages.append(vendored_pkg)

            except Exception as e:
                # Include dependency chain in error message
                chain = dependency_graph.get_dependency_chain(pkg_name)
                chain_str = " -> ".join(chain) if chain else pkg_name
                result.errors.append(
                    f"Failed to vendor '{pkg_name}':\n"
                    f"  Dependency chain: {chain_str}\n"
                    f"  Error: {e}"
                )

    # Create __init__.py in vendor directory if it doesn't exist
    init_file = Path(target_dir) / "__init__.py"
    if not init_file.exists():
        init_file.write_text(
            "# SPDX-License-Identifier: MIT\n"
            '"""Vendored dependencies for this Island package."""\n',
            encoding="utf-8",
        )

    # Compute platform information from the dependency graph
    result.is_pure_python = dependency_graph.is_pure_python()
    result.platform_tag = dependency_graph.get_most_restrictive_tag()

    return result


def create_vendor_manifest(
    result: VendorResult,
    output_path: str | Path,
) -> None:
    """Create a manifest file listing vendored packages.

    This creates a JSON file that records which packages were vendored
    and their versions, useful for debugging and auditing. The manifest
    includes dependency graph information and platform tags.

    Args:
        result: VendorResult from vendor_dependencies
        output_path: Path to write the manifest file
    """
    # Build vendored_packages with enhanced information
    vendored_packages: dict[str, dict] = {}
    dependency_graph_data: dict[str, list[str]] = {}
    root_dependencies: list[str] = []

    # If we have a dependency graph, use it for enhanced information
    if result.dependency_graph is not None:
        root_dependencies = list(result.dependency_graph.root_dependencies)

        for pkg_name, resolved_pkg in result.dependency_graph.packages.items():
            vendored_packages[pkg_name] = {
                "version": resolved_pkg.version,
                "modules": [],  # Will be filled from VendoredPackage if available
                "is_pure_python": resolved_pkg.is_pure_python,
                "platform_tags": resolved_pkg.platform_tags,
                "direct_dependencies": resolved_pkg.requires,
            }
            dependency_graph_data[pkg_name] = resolved_pkg.requires

        # Merge module information from VendoredPackage
        for pkg in result.packages:
            if pkg.name in vendored_packages:
                vendored_packages[pkg.name]["modules"] = pkg.top_level_modules
            else:
                # Package not in dependency graph, add it
                vendored_packages[pkg.name] = {
                    "version": pkg.version,
                    "modules": pkg.top_level_modules,
                    "is_pure_python": True,  # Default assumption
                    "platform_tags": [],
                    "direct_dependencies": [],
                }
                dependency_graph_data[pkg.name] = []
    else:
        # No dependency graph, use basic information from packages
        for pkg in result.packages:
            vendored_packages[pkg.name] = {
                "version": pkg.version,
                "modules": pkg.top_level_modules,
                "is_pure_python": True,  # Default assumption without graph
                "platform_tags": [],
                "direct_dependencies": [],
            }
            dependency_graph_data[pkg.name] = []

    # Build the manifest
    manifest: dict = {
        "vendored_packages": vendored_packages,
        "dependency_graph": dependency_graph_data,
        "root_dependencies": root_dependencies,
        "is_pure_python": result.is_pure_python,
        "effective_platform_tag": str(result.platform_tag) if result.platform_tag else None,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
