# SPDX-License-Identifier: MIT
"""Semantic version parsing for APWorld packages.

Supports MAJOR.MINOR.PATCH format with optional pre-release and build metadata:
- Pre-release: -alpha, -alpha.1, -beta, -beta.2, -rc, -rc.1
- Build metadata: +build, +build.123, +20240101
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Semantic versioning regex pattern (SemVer 2.0.0 compliant)
# https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class InvalidVersionError(Exception):
    """Raised when a version string does not follow semantic versioning."""

    def __init__(self, version: str, message: str = ""):
        self.version = version
        self.message = message or f"Invalid semantic version: {version}"
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class Version:
    """Represents a parsed semantic version.

    Attributes:
        major: Major version number (breaking changes)
        minor: Minor version number (new features, backward compatible)
        patch: Patch version number (bug fixes, backward compatible)
        prerelease: Optional pre-release identifier (e.g., "alpha.1", "beta", "rc.2")
        build: Optional build metadata (e.g., "build.123", "20240101")
    """

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    def __str__(self) -> str:
        """Return the canonical string representation of the version."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    @property
    def is_prerelease(self) -> bool:
        """Return True if this is a pre-release version."""
        return self.prerelease is not None

    @property
    def base_version(self) -> str:
        """Return the base version without pre-release or build metadata."""
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_version(version_string: str) -> Version:
    """Parse a semantic version string into a Version object.

    Args:
        version_string: A string following semantic versioning format
            (MAJOR.MINOR.PATCH[-prerelease][+build])

    Returns:
        A Version object with parsed components

    Raises:
        InvalidVersionError: If the string does not follow semantic versioning

    Examples:
        >>> parse_version("1.2.3")
        Version(major=1, minor=2, patch=3, prerelease=None, build=None)

        >>> parse_version("1.0.0-alpha.1")
        Version(major=1, minor=0, patch=0, prerelease='alpha.1', build=None)

        >>> parse_version("2.0.0-rc.1+build.456")
        Version(major=2, minor=0, patch=0, prerelease='rc.1', build='456')
    """
    if not isinstance(version_string, str):
        raise InvalidVersionError(
            str(version_string), f"Version must be a string, got {type(version_string).__name__}"
        )

    version_string = version_string.strip()
    if not version_string:
        raise InvalidVersionError(version_string, "Version string cannot be empty")

    match = SEMVER_PATTERN.match(version_string)
    if not match:
        raise InvalidVersionError(version_string)

    return Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=match.group("prerelease"),
        build=match.group("buildmetadata"),
    )


def is_valid_semver(version_string: str) -> bool:
    """Check if a string is a valid semantic version.

    Args:
        version_string: The string to validate

    Returns:
        True if the string is a valid semantic version, False otherwise

    Examples:
        >>> is_valid_semver("1.0.0")
        True
        >>> is_valid_semver("1.0")
        False
        >>> is_valid_semver("1.0.0-alpha")
        True
    """
    if not isinstance(version_string, str):
        return False
    return SEMVER_PATTERN.match(version_string.strip()) is not None
