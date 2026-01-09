# SPDX-License-Identifier: MIT
"""Distribution building for APWorld packages (.apworld, .tar.gz).

This package provides utilities for building APWorld distributions:
- Binary distributions (.apworld) - ZIP archives with compiled code
- Source distributions (.tar.gz) - archives with source files
- PEP 427 wheel naming conventions for filenames

Example:
    >>> from apworld_build import build_apworld, build_sdist, BuildConfig
    >>>
    >>> # Load configuration from pyproject.toml
    >>> config = BuildConfig.from_pyproject("pyproject.toml")
    >>>
    >>> # Build binary distribution (.apworld)
    >>> result = build_apworld(config, output_dir="dist/")
    >>> result.path
    PosixPath('dist/my_game-1.0.0-py3-none-any.apworld')
    >>>
    >>> # Build source distribution (.tar.gz)
    >>> result = build_sdist(config, output_dir="dist/")
    >>> result.path
    PosixPath('dist/my_game-1.0.0.tar.gz')
"""

__version__ = "0.1.0"

from .apworld import (
    ApworldError,
    ApworldResult,
    build_apworld,
    build_apworld_with_vendoring,
)
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
    ParsedApworldFilename,
    ParsedSdistFilename,
    PlatformTag,
    build_apworld_filename,
    build_sdist_filename,
    is_pure_python_tag,
    normalize_name,
    normalize_version,
    parse_apworld_filename,
    parse_sdist_filename,
)
from .sdist import (
    SdistConfig,
    SdistError,
    SdistResult,
    build_sdist,
    build_sdist_from_directory,
    collect_source_files,
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
    "PlatformTag",
    "ParsedApworldFilename",
    "ParsedSdistFilename",
    "UNIVERSAL_TAG",
    "WINDOWS_X64_TAG",
    "WINDOWS_ARM64_TAG",
    "MACOS_X64_TAG",
    "MACOS_ARM64_TAG",
    "LINUX_X64_TAG",
    "LINUX_ARM64_TAG",
    "build_apworld_filename",
    "build_sdist_filename",
    "parse_apworld_filename",
    "parse_sdist_filename",
    "normalize_name",
    "normalize_version",
    "is_pure_python_tag",
    # APWorld builder
    "ApworldError",
    "ApworldResult",
    "build_apworld",
    "build_apworld_with_vendoring",
    # Sdist builder
    "SdistConfig",
    "SdistError",
    "SdistResult",
    "build_sdist",
    "build_sdist_from_directory",
    "collect_source_files",
]
