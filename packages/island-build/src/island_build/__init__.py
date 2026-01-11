# SPDX-License-Identifier: MIT
"""Distribution building for Island packages (.island, .tar.gz).

This package provides utilities for building Island distributions:
- Binary distributions (.island) - ZIP archives with compiled code
- Source distributions (.tar.gz) - archives with source files
- PEP 427 wheel naming conventions for filenames

Example:
    >>> from island_build import build_island, build_sdist, BuildConfig
    >>>
    >>> # Load configuration from pyproject.toml
    >>> config = BuildConfig.from_pyproject("pyproject.toml")
    >>>
    >>> # Build binary distribution (.island)
    >>> result = build_island(config, output_dir="dist/")
    >>> result.path
    PosixPath('dist/my_game-1.0.0-py3-none-any.island')
    >>>
    >>> # Build source distribution (.tar.gz)
    >>> result = build_sdist(config, output_dir="dist/")
    >>> result.path
    PosixPath('dist/my_game-1.0.0.tar.gz')
"""

__version__ = "0.1.0"

from .config import (
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_INCLUDE_PATTERNS,
    DEFAULT_SCHEMA_VERSION,
    MIN_COMPATIBLE_VERSION,
    BuildConfig,
    BuildConfigError,
)
from .filename import (
    LINUX_ARM64_TAG,
    LINUX_X64_TAG,
    MACOS_ARM64_TAG,
    MACOS_X64_TAG,
    UNIVERSAL_TAG,
    WINDOWS_ARM64_TAG,
    WINDOWS_X64_TAG,
    FilenameError,
    IslandFilename,
    ParsedIslandFilename,
    ParsedSdistFilename,
    PlatformTag,
    build_island_filename,
    build_sdist_filename,
    is_pure_python_tag,
    normalize_name,
    normalize_version,
    parse_island_filename,
    parse_sdist_filename,
)
from .island import (
    ENTRY_POINT_PATTERN,
    InvalidEntryPointError,
    IslandError,
    IslandResult,
    MissingEntryPointError,
    build_island,
    build_island_with_vendoring,
    extract_entry_points_from_pyproject,
    validate_entry_point_format,
    validate_entry_points,
)
from .sdist import (
    SdistConfig,
    SdistError,
    SdistResult,
    build_sdist,
    build_sdist_from_directory,
    collect_source_files,
)
from .wheel import (
    GENERATOR,
    WHEEL_VERSION,
    EntryPointsFile,
    PackageMetadata,
    RecordEntry,
    RecordFile,
    WheelMetadata,
    compute_content_hash,
    compute_file_hash,
    get_dist_info_name,
)

__all__ = [
    # Config
    "BuildConfig",
    "BuildConfigError",
    "DEFAULT_EXCLUDE_PATTERNS",
    "DEFAULT_INCLUDE_PATTERNS",
    "DEFAULT_SCHEMA_VERSION",
    "MIN_COMPATIBLE_VERSION",
    # Filename
    "FilenameError",
    "IslandFilename",
    "PlatformTag",
    "ParsedIslandFilename",
    "ParsedSdistFilename",
    "UNIVERSAL_TAG",
    "WINDOWS_X64_TAG",
    "WINDOWS_ARM64_TAG",
    "MACOS_X64_TAG",
    "MACOS_ARM64_TAG",
    "LINUX_X64_TAG",
    "LINUX_ARM64_TAG",
    "build_island_filename",
    "build_sdist_filename",
    "parse_island_filename",
    "parse_sdist_filename",
    "normalize_name",
    "normalize_version",
    "is_pure_python_tag",
    # Island builder
    "ENTRY_POINT_PATTERN",
    "InvalidEntryPointError",
    "IslandError",
    "IslandResult",
    "MissingEntryPointError",
    "build_island",
    "build_island_with_vendoring",
    "extract_entry_points_from_pyproject",
    "validate_entry_point_format",
    "validate_entry_points",
    # Sdist builder
    "SdistConfig",
    "SdistError",
    "SdistResult",
    "build_sdist",
    "build_sdist_from_directory",
    "collect_source_files",
    # Wheel metadata
    "GENERATOR",
    "WHEEL_VERSION",
    "WheelMetadata",
    "PackageMetadata",
    "RecordEntry",
    "RecordFile",
    "EntryPointsFile",
    "compute_file_hash",
    "compute_content_hash",
    "get_dist_info_name",
]
