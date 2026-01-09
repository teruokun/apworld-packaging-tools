# SPDX-License-Identifier: MIT
"""Dependency vendoring packager for APWorld packages.

This module downloads and extracts Python dependencies into a vendor directory,
preparing them for inclusion in APWorld packages.
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
    config: "VendorConfig",
    target_dir: str | Path,
    python_executable: str | None = None,
) -> VendorResult:
    """Vendor dependencies into a target directory.

    This function:
    1. Downloads dependencies using pip
    2. Extracts them to the target directory
    3. Tracks which packages were vendored

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

    # Filter dependencies based on config
    deps_to_vendor: list[str] = []
    for dep in config.dependencies:
        pkg_name = _parse_requirement(dep)
        if config.should_vendor(pkg_name):
            deps_to_vendor.append(dep)

    if not deps_to_vendor:
        return result

    # Create a temporary directory for downloading
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            download_dependencies(
                deps_to_vendor,
                temp_path,
                python_executable,
            )
        except DependencyDownloadError as e:
            result.errors.append(str(e))
            return result

        # Process each downloaded package
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        for dep in deps_to_vendor:
            pkg_name = _parse_requirement(dep)

            try:
                # Get package info
                version = _get_package_version(temp_path, pkg_name)
                top_level = _get_top_level_modules(temp_path)

                # Filter to modules that match this package
                # (temp_path may contain multiple packages)
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
                result.errors.append(f"Failed to vendor {pkg_name}: {e}")

    # Create __init__.py in vendor directory if it doesn't exist
    init_file = Path(target_dir) / "__init__.py"
    if not init_file.exists():
        init_file.write_text(
            "# SPDX-License-Identifier: MIT\n"
            '"""Vendored dependencies for this APWorld package."""\n',
            encoding="utf-8",
        )

    return result


def create_vendor_manifest(
    result: VendorResult,
    output_path: str | Path,
) -> None:
    """Create a manifest file listing vendored packages.

    This creates a JSON file that records which packages were vendored
    and their versions, useful for debugging and auditing.

    Args:
        result: VendorResult from vendor_dependencies
        output_path: Path to write the manifest file
    """
    manifest = {
        "vendored_packages": {
            pkg.name: {
                "version": pkg.version,
                "modules": pkg.top_level_modules,
            }
            for pkg in result.packages
        }
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
