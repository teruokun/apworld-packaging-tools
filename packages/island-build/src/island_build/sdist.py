# SPDX-License-Identifier: MIT
"""Source distribution builder for Island packages.

This module creates source distributions (.tar.gz) containing all source files
needed to build an Island package.
"""

from __future__ import annotations

import fnmatch
import os
import tarfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from .filename import build_sdist_filename

if TYPE_CHECKING:
    from .config import BuildConfig


class SdistError(Exception):
    """Raised when source distribution building fails."""

    pass


# Default files to always include if they exist
DEFAULT_INCLUDE_FILES = [
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "LICENSE",
    "LICENSE.txt",
    "LICENSE.md",
    "COPYING",
    "CHANGELOG.md",
    "CHANGELOG.rst",
    "CHANGELOG.txt",
    "CHANGELOG",
    "HISTORY.md",
    "HISTORY.rst",
    "island.json",
]

# Default patterns to exclude
DEFAULT_EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".git",
    ".git/*",
    ".gitignore",
    ".gitattributes",
    ".hg",
    ".hg/*",
    ".svn",
    ".svn/*",
    ".tox",
    ".tox/*",
    ".nox",
    ".nox/*",
    ".pytest_cache",
    ".pytest_cache/*",
    ".mypy_cache",
    ".mypy_cache/*",
    ".ruff_cache",
    ".ruff_cache/*",
    "*.egg-info",
    "*.egg-info/*",
    "dist",
    "dist/*",
    "build",
    "build/*",
    ".eggs",
    ".eggs/*",
    "*.so",
    "*.dylib",
    "*.dll",
    ".DS_Store",
    "Thumbs.db",
    "*.swp",
    "*.swo",
    "*~",
    ".venv",
    ".venv/*",
    "venv",
    "venv/*",
    ".env",
    ".env/*",
    "env",
    "env/*",
]


@dataclass
class SdistConfig:
    """Configuration for source distribution building.

    Attributes:
        source_dir: Root directory containing source files
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        include_files: Specific files to always include
    """

    source_dir: Path
    include_patterns: list[str] = field(default_factory=lambda: ["*.py", "**/*.py"])
    exclude_patterns: list[str] = field(default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy())
    include_files: list[str] = field(default_factory=lambda: DEFAULT_INCLUDE_FILES.copy())


@dataclass
class SdistResult:
    """Result of source distribution building.

    Attributes:
        path: Path to the created .tar.gz file
        filename: Name of the created file
        files_included: List of files included in the archive
        size: Size of the archive in bytes
    """

    path: Path
    filename: str
    files_included: list[str]
    size: int


def _matches_any_pattern(path: str, patterns: list[str]) -> bool:
    """Check if a path matches any of the given glob patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        # Also check just the filename
        if fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    return False


def _should_include_file(
    rel_path: str,
    include_patterns: list[str],
    exclude_patterns: list[str],
    include_files: list[str],
) -> bool:
    """Determine if a file should be included in the sdist."""
    filename = os.path.basename(rel_path)

    # Always exclude if matches exclude pattern
    if _matches_any_pattern(rel_path, exclude_patterns):
        return False

    # Always include specific files
    if filename in include_files:
        return True

    # Include if matches include pattern
    if _matches_any_pattern(rel_path, include_patterns):
        return True

    return False


def collect_source_files(
    source_dir: Path,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
    include_files: Optional[list[str]] = None,
) -> list[Path]:
    """Collect all source files to include in the distribution.

    Args:
        source_dir: Root directory to collect files from
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        include_files: Specific files to always include

    Returns:
        List of paths to include (relative to source_dir)
    """
    include_patterns = include_patterns or ["*.py", "**/*.py"]
    exclude_patterns = exclude_patterns or DEFAULT_EXCLUDE_PATTERNS.copy()
    include_files = include_files or DEFAULT_INCLUDE_FILES.copy()

    collected: list[Path] = []

    for root, dirs, files in os.walk(source_dir):
        # Filter directories to avoid walking into excluded ones
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

            if _should_include_file(
                rel_path_str,
                include_patterns,
                exclude_patterns,
                include_files,
            ):
                collected.append(rel_path)

    return sorted(collected)


def build_sdist(
    config: "BuildConfig",
    output_dir: str | Path,
    source_dir: Optional[str | Path] = None,
) -> SdistResult:
    """Build a source distribution (.tar.gz) for an Island package.

    Args:
        config: Build configuration with package metadata
        output_dir: Directory to write the .tar.gz file
        source_dir: Source directory (defaults to config.source_dir)

    Returns:
        SdistResult with information about the created archive

    Raises:
        SdistError: If building fails
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    src_dir = Path(source_dir) if source_dir else config.source_dir
    if not src_dir.exists():
        raise SdistError(f"Source directory does not exist: {src_dir}")

    # Generate filename
    filename = build_sdist_filename(config.name, config.version)
    archive_path = output_path / filename

    # Collect files to include
    files = collect_source_files(
        src_dir,
        include_patterns=config.include_patterns,
        exclude_patterns=config.exclude_patterns,
    )

    if not files:
        raise SdistError(f"No source files found in {src_dir}")

    # Create the archive
    # The archive structure is: {name}-{version}/{files}
    archive_prefix = f"{config.normalized_name}-{config.version}"

    files_included: list[str] = []

    with tarfile.open(archive_path, "w:gz") as tar:
        for rel_path in files:
            full_path = src_dir / rel_path
            arcname = f"{archive_prefix}/{rel_path}"

            tar.add(full_path, arcname=arcname)
            files_included.append(str(rel_path))

    return SdistResult(
        path=archive_path,
        filename=filename,
        files_included=files_included,
        size=archive_path.stat().st_size,
    )


def build_sdist_from_directory(
    source_dir: str | Path,
    name: str,
    version: str,
    output_dir: str | Path,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> SdistResult:
    """Build a source distribution from a directory without a BuildConfig.

    This is a convenience function for simple use cases.

    Args:
        source_dir: Directory containing source files
        name: Package name
        version: Package version
        output_dir: Directory to write the .tar.gz file
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude

    Returns:
        SdistResult with information about the created archive

    Raises:
        SdistError: If building fails
    """
    from .filename import normalize_name

    src_dir = Path(source_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        raise SdistError(f"Source directory does not exist: {src_dir}")

    # Generate filename
    filename = build_sdist_filename(name, version)
    archive_path = output_path / filename

    # Collect files
    files = collect_source_files(
        src_dir,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )

    if not files:
        raise SdistError(f"No source files found in {src_dir}")

    # Create archive
    normalized_name = normalize_name(name)
    archive_prefix = f"{normalized_name}-{version}"

    files_included: list[str] = []

    with tarfile.open(archive_path, "w:gz") as tar:
        for rel_path in files:
            full_path = src_dir / rel_path
            arcname = f"{archive_prefix}/{rel_path}"

            tar.add(full_path, arcname=arcname)
            files_included.append(str(rel_path))

    return SdistResult(
        path=archive_path,
        filename=filename,
        files_included=files_included,
        size=archive_path.stat().st_size,
    )
