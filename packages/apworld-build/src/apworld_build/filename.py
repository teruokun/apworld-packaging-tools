# SPDX-License-Identifier: MIT
"""Filename conventions for APWorld distributions.

This module implements PEP 427 wheel naming conventions adapted for APWorld packages:
- Binary: {name}-{version}-{python}-{abi}-{platform}.apworld
- Source: {name}-{version}.tar.gz

References:
- PEP 427: https://peps.python.org/pep-0427/
- PEP 425: https://peps.python.org/pep-0425/
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


class FilenameError(Exception):
    """Raised when filename generation or parsing fails."""

    pass


# Pattern for valid distribution names (PEP 427)
# Names must be alphanumeric with underscores (hyphens converted to underscores)
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_]*$")

# Pattern for parsing apworld filenames
APWORLD_PATTERN = re.compile(
    r"^(?P<name>[a-zA-Z0-9][a-zA-Z0-9_]*)"
    r"-(?P<version>[^-]+)"
    r"-(?P<python>[a-z0-9]+)"
    r"-(?P<abi>[a-z0-9_]+)"
    r"-(?P<platform>[a-z0-9_]+)"
    r"\.apworld$"
)

# Pattern for parsing sdist filenames
SDIST_PATTERN = re.compile(
    r"^(?P<name>[a-zA-Z0-9][a-zA-Z0-9_]*)" r"-(?P<version>[^/]+)" r"\.tar\.gz$"
)


def normalize_name(name: str) -> str:
    """Normalize a package name for use in filenames.

    Following PEP 427, package names are normalized by:
    - Converting to lowercase
    - Replacing hyphens, periods, and spaces with underscores
    - Collapsing multiple underscores

    Args:
        name: The package name to normalize

    Returns:
        Normalized package name suitable for filenames

    Raises:
        FilenameError: If the name is empty or invalid

    Examples:
        >>> normalize_name("Pokemon-Emerald")
        'pokemon_emerald'
        >>> normalize_name("my.game.world")
        'my_game_world'
    """
    if not name:
        raise FilenameError("Package name cannot be empty")

    # Convert to lowercase and replace separators with underscores
    normalized = name.lower()
    normalized = re.sub(r"[-.\s]+", "_", normalized)
    # Collapse multiple underscores
    normalized = re.sub(r"_+", "_", normalized)
    # Remove leading/trailing underscores
    normalized = normalized.strip("_")

    if not normalized:
        raise FilenameError(f"Invalid package name: {name}")

    if not NAME_PATTERN.match(normalized):
        raise FilenameError(f"Invalid package name after normalization: {normalized}")

    return normalized


def normalize_version(version: str) -> str:
    """Normalize a version string for use in filenames.

    Following PEP 427, version strings are normalized by:
    - Replacing hyphens with underscores (for pre-release separators)

    Args:
        version: The version string to normalize

    Returns:
        Normalized version string suitable for filenames

    Raises:
        FilenameError: If the version is empty

    Examples:
        >>> normalize_version("1.0.0-alpha.1")
        '1.0.0_alpha.1'
        >>> normalize_version("2.0.0+build.123")
        '2.0.0+build.123'
    """
    if not version:
        raise FilenameError("Version cannot be empty")

    # Replace hyphens with underscores (pre-release separator)
    return version.replace("-", "_")


@dataclass(frozen=True, slots=True)
class PlatformTag:
    """Represents a platform compatibility tag (PEP 425).

    Attributes:
        python: Python implementation and version (e.g., "py3", "cp311")
        abi: ABI tag (e.g., "none", "cp311", "abi3")
        platform: Platform tag (e.g., "any", "win_amd64", "macosx_11_0_arm64")
    """

    python: str
    abi: str
    platform: str

    def __str__(self) -> str:
        """Return the tag as a string."""
        return f"{self.python}-{self.abi}-{self.platform}"

    @classmethod
    def universal(cls) -> "PlatformTag":
        """Create a universal tag for pure Python packages.

        Returns:
            PlatformTag with py3-none-any
        """
        return cls(python="py3", abi="none", platform="any")

    @classmethod
    def from_string(cls, tag_string: str) -> "PlatformTag":
        """Parse a platform tag string.

        Args:
            tag_string: Tag in format "python-abi-platform"

        Returns:
            Parsed PlatformTag

        Raises:
            FilenameError: If the tag string is invalid
        """
        parts = tag_string.split("-")
        if len(parts) != 3:
            raise FilenameError(f"Invalid platform tag: {tag_string}")
        return cls(python=parts[0], abi=parts[1], platform=parts[2])


# Common platform tags
UNIVERSAL_TAG = PlatformTag.universal()

# Platform-specific tags for common platforms
WINDOWS_X64_TAG = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
WINDOWS_ARM64_TAG = PlatformTag(python="cp311", abi="cp311", platform="win_arm64")
MACOS_X64_TAG = PlatformTag(python="cp311", abi="cp311", platform="macosx_11_0_x86_64")
MACOS_ARM64_TAG = PlatformTag(python="cp311", abi="cp311", platform="macosx_11_0_arm64")
LINUX_X64_TAG = PlatformTag(python="cp311", abi="cp311", platform="manylinux_2_17_x86_64")
LINUX_ARM64_TAG = PlatformTag(python="cp311", abi="cp311", platform="manylinux_2_17_aarch64")


def build_apworld_filename(
    name: str,
    version: str,
    tag: Optional[PlatformTag] = None,
) -> str:
    """Build an APWorld filename following PEP 427 conventions.

    Args:
        name: Package name
        version: Package version (semver)
        tag: Platform tag (defaults to universal py3-none-any)

    Returns:
        Filename in format: {name}-{version}-{python}-{abi}-{platform}.apworld

    Raises:
        FilenameError: If name or version is invalid

    Examples:
        >>> build_apworld_filename("pokemon-emerald", "1.0.0")
        'pokemon_emerald-1.0.0-py3-none-any.apworld'

        >>> build_apworld_filename("my-game", "2.0.0-alpha.1")
        'my_game-2.0.0_alpha.1-py3-none-any.apworld'
    """
    tag = tag or UNIVERSAL_TAG
    norm_name = normalize_name(name)
    norm_version = normalize_version(version)

    return f"{norm_name}-{norm_version}-{tag.python}-{tag.abi}-{tag.platform}.apworld"


def build_sdist_filename(name: str, version: str) -> str:
    """Build a source distribution filename.

    Args:
        name: Package name
        version: Package version (semver)

    Returns:
        Filename in format: {name}-{version}.tar.gz

    Raises:
        FilenameError: If name or version is invalid

    Examples:
        >>> build_sdist_filename("pokemon-emerald", "1.0.0")
        'pokemon_emerald-1.0.0.tar.gz'
    """
    norm_name = normalize_name(name)
    norm_version = normalize_version(version)

    return f"{norm_name}-{norm_version}.tar.gz"


@dataclass(frozen=True, slots=True)
class ParsedApworldFilename:
    """Parsed components of an APWorld filename.

    Attributes:
        name: Normalized package name
        version: Package version
        tag: Platform compatibility tag
    """

    name: str
    version: str
    tag: PlatformTag


@dataclass(frozen=True, slots=True)
class ParsedSdistFilename:
    """Parsed components of a source distribution filename.

    Attributes:
        name: Normalized package name
        version: Package version
    """

    name: str
    version: str


def parse_apworld_filename(filename: str) -> ParsedApworldFilename:
    """Parse an APWorld filename into its components.

    Args:
        filename: APWorld filename to parse

    Returns:
        ParsedApworldFilename with extracted components

    Raises:
        FilenameError: If the filename doesn't match expected format

    Examples:
        >>> parsed = parse_apworld_filename("pokemon_emerald-1.0.0-py3-none-any.apworld")
        >>> parsed.name
        'pokemon_emerald'
        >>> parsed.version
        '1.0.0'
    """
    match = APWORLD_PATTERN.match(filename)
    if not match:
        raise FilenameError(f"Invalid APWorld filename: {filename}")

    return ParsedApworldFilename(
        name=match.group("name"),
        version=match.group("version"),
        tag=PlatformTag(
            python=match.group("python"),
            abi=match.group("abi"),
            platform=match.group("platform"),
        ),
    )


def parse_sdist_filename(filename: str) -> ParsedSdistFilename:
    """Parse a source distribution filename into its components.

    Args:
        filename: Source distribution filename to parse

    Returns:
        ParsedSdistFilename with extracted components

    Raises:
        FilenameError: If the filename doesn't match expected format

    Examples:
        >>> parsed = parse_sdist_filename("pokemon_emerald-1.0.0.tar.gz")
        >>> parsed.name
        'pokemon_emerald'
        >>> parsed.version
        '1.0.0'
    """
    match = SDIST_PATTERN.match(filename)
    if not match:
        raise FilenameError(f"Invalid sdist filename: {filename}")

    return ParsedSdistFilename(
        name=match.group("name"),
        version=match.group("version"),
    )


def is_pure_python_tag(tag: PlatformTag) -> bool:
    """Check if a platform tag indicates a pure Python package.

    Args:
        tag: Platform tag to check

    Returns:
        True if the tag indicates pure Python (py3-none-any or similar)

    Examples:
        >>> is_pure_python_tag(UNIVERSAL_TAG)
        True
        >>> is_pure_python_tag(WINDOWS_X64_TAG)
        False
    """
    return tag.abi == "none" and tag.platform == "any"
