# SPDX-License-Identifier: MIT
"""Semantic version parsing and comparison for APWorld packages.

This package provides utilities for parsing and comparing semantic versions
following the SemVer 2.0.0 specification with PEP 440 ordering semantics.

Example:
    >>> from apworld_version import parse_version, compare_versions, is_valid_semver
    >>> 
    >>> version = parse_version("1.2.3-alpha.1+build.456")
    >>> version.major
    1
    >>> version.prerelease
    'alpha.1'
    >>> 
    >>> is_valid_semver("1.0.0")
    True
    >>> 
    >>> compare_versions("1.0.0", "2.0.0")
    -1
"""

__version__ = "0.1.0"

from .semver import (
    Version,
    parse_version,
    is_valid_semver,
    InvalidVersionError,
    SEMVER_PATTERN,
)
from .compare import (
    compare_versions,
    version_key,
)

__all__ = [
    # Version parsing
    "Version",
    "parse_version",
    "is_valid_semver",
    "InvalidVersionError",
    "SEMVER_PATTERN",
    # Version comparison
    "compare_versions",
    "version_key",
]
