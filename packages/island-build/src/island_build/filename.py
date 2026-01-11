# SPDX-License-Identifier: MIT
"""Filename conventions for Island distributions.

This module implements PEP 427 wheel naming conventions adapted for Island packages:
- Binary: {name}-{version}-{python}-{abi}-{platform}.island
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

# Pattern for parsing island filenames (with optional build tag)
# Format: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.island
ISLAND_PATTERN = re.compile(
    r"^(?P<name>[a-zA-Z0-9][a-zA-Z0-9_]*)"
    r"-(?P<version>[^-]+)"
    r"(?:-(?P<build>\d+))?"
    r"-(?P<python>[a-z0-9]+)"
    r"-(?P<abi>[a-z0-9_]+)"
    r"-(?P<platform>[a-z0-9_]+)"
    r"\.island$"
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
    def universal(cls) -> PlatformTag:
        """Create a universal tag for pure Python packages.

        Returns:
            PlatformTag with py3-none-any
        """
        return cls(python="py3", abi="none", platform="any")

    @classmethod
    def pure_python(cls) -> PlatformTag:
        """Create a tag for pure Python packages.

        This is an alias for universal() that matches the design specification.

        Returns:
            PlatformTag with py3-none-any
        """
        return cls.universal()

    @classmethod
    def from_string(cls, tag_string: str) -> PlatformTag:
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

    @classmethod
    def parse(cls, tag_string: str) -> PlatformTag:
        """Parse a platform tag string.

        This is an alias for from_string() that matches the design specification.

        Args:
            tag_string: Tag in format "python-abi-platform"

        Returns:
            Parsed PlatformTag

        Raises:
            FilenameError: If the tag string is invalid
        """
        return cls.from_string(tag_string)


@dataclass(frozen=True, slots=True)
class IslandFilename:
    """Represents a complete Island filename with all components.

    This dataclass provides both construction and parsing of Island filenames
    following the PEP 427 wheel naming convention with the .island extension.

    Filename format: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.island

    Attributes:
        distribution: Normalized package/distribution name
        version: Package version (normalized, hyphens replaced with underscores)
        build_tag: Optional build number (numeric string, e.g., "1", "2")
        platform_tag: Platform compatibility tag (python-abi-platform)

    Examples:
        >>> # Create a filename
        >>> fn = IslandFilename(
        ...     distribution="pokemon_emerald",
        ...     version="1.0.0",
        ...     build_tag=None,
        ...     platform_tag=PlatformTag.pure_python()
        ... )
        >>> str(fn)
        'pokemon_emerald-1.0.0-py3-none-any.island'

        >>> # Parse a filename
        >>> fn = IslandFilename.parse("my_game-2.0.0-1-cp311-cp311-win_amd64.island")
        >>> fn.distribution
        'my_game'
        >>> fn.build_tag
        '1'
    """

    distribution: str
    version: str
    build_tag: str | None
    platform_tag: PlatformTag

    def __str__(self) -> str:
        """Generate the full filename string.

        Returns:
            Complete filename with .island extension

        Examples:
            >>> fn = IslandFilename("my_game", "1.0.0", None, PlatformTag.pure_python())
            >>> str(fn)
            'my_game-1.0.0-py3-none-any.island'

            >>> fn = IslandFilename("my_game", "1.0.0", "1", PlatformTag.pure_python())
            >>> str(fn)
            'my_game-1.0.0-1-py3-none-any.island'
        """
        parts = [self.distribution, self.version]
        if self.build_tag:
            parts.append(self.build_tag)
        parts.append(str(self.platform_tag))
        return "-".join(parts) + ".island"

    @classmethod
    def parse(cls, filename: str) -> IslandFilename:
        """Parse an Island filename into its components.

        Args:
            filename: Island filename to parse (e.g., "my_game-1.0.0-py3-none-any.island")

        Returns:
            IslandFilename with extracted components

        Raises:
            FilenameError: If the filename doesn't match expected format

        Examples:
            >>> fn = IslandFilename.parse("pokemon_emerald-1.0.0-py3-none-any.island")
            >>> fn.distribution
            'pokemon_emerald'
            >>> fn.version
            '1.0.0'
            >>> fn.build_tag is None
            True

            >>> fn = IslandFilename.parse("complex_world-3.0.0-1-py3-none-linux_x86_64.island")
            >>> fn.build_tag
            '1'
        """
        match = ISLAND_PATTERN.match(filename)
        if not match:
            raise FilenameError(f"Invalid Island filename: {filename}")

        return cls(
            distribution=match.group("name"),
            version=match.group("version"),
            build_tag=match.group("build"),  # Will be None if not present
            platform_tag=PlatformTag(
                python=match.group("python"),
                abi=match.group("abi"),
                platform=match.group("platform"),
            ),
        )

    @classmethod
    def from_parts(
        cls,
        name: str,
        version: str,
        build_tag: str | None = None,
        platform_tag: PlatformTag | None = None,
    ) -> IslandFilename:
        """Create an IslandFilename from raw parts, normalizing as needed.

        This is a convenience method that handles name and version normalization.

        Args:
            name: Package name (will be normalized)
            version: Package version (will be normalized)
            build_tag: Optional build number
            platform_tag: Platform tag (defaults to pure Python)

        Returns:
            IslandFilename with normalized components

        Raises:
            FilenameError: If name or version is invalid

        Examples:
            >>> fn = IslandFilename.from_parts("Pokemon-Emerald", "1.0.0-alpha")
            >>> str(fn)
            'pokemon_emerald-1.0.0_alpha-py3-none-any.island'
        """
        return cls(
            distribution=normalize_name(name),
            version=normalize_version(version),
            build_tag=build_tag,
            platform_tag=platform_tag or PlatformTag.pure_python(),
        )


# Common platform tags
UNIVERSAL_TAG = PlatformTag.universal()

# Platform-specific tags for common platforms
WINDOWS_X64_TAG = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
WINDOWS_ARM64_TAG = PlatformTag(python="cp311", abi="cp311", platform="win_arm64")
MACOS_X64_TAG = PlatformTag(python="cp311", abi="cp311", platform="macosx_11_0_x86_64")
MACOS_ARM64_TAG = PlatformTag(python="cp311", abi="cp311", platform="macosx_11_0_arm64")
LINUX_X64_TAG = PlatformTag(python="cp311", abi="cp311", platform="manylinux_2_17_x86_64")
LINUX_ARM64_TAG = PlatformTag(python="cp311", abi="cp311", platform="manylinux_2_17_aarch64")


def build_island_filename(
    name: str,
    version: str,
    tag: Optional[PlatformTag] = None,
) -> str:
    """Build an Island filename following PEP 427 conventions.

    Args:
        name: Package name
        version: Package version (semver)
        tag: Platform tag (defaults to universal py3-none-any)

    Returns:
        Filename in format: {name}-{version}-{python}-{abi}-{platform}.island

    Raises:
        FilenameError: If name or version is invalid

    Examples:
        >>> build_island_filename("pokemon-emerald", "1.0.0")
        'pokemon_emerald-1.0.0-py3-none-any.island'

        >>> build_island_filename("my-game", "2.0.0-alpha.1")
        'my_game-2.0.0_alpha.1-py3-none-any.island'
    """
    tag = tag or UNIVERSAL_TAG
    norm_name = normalize_name(name)
    norm_version = normalize_version(version)

    return f"{norm_name}-{norm_version}-{tag.python}-{tag.abi}-{tag.platform}.island"


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
class ParsedIslandFilename:
    """Parsed components of an Island filename.

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


def parse_island_filename(filename: str) -> ParsedIslandFilename:
    """Parse an Island filename into its components.

    Args:
        filename: Island filename to parse

    Returns:
        ParsedIslandFilename with extracted components

    Raises:
        FilenameError: If the filename doesn't match expected format

    Examples:
        >>> parsed = parse_island_filename("pokemon_emerald-1.0.0-py3-none-any.island")
        >>> parsed.name
        'pokemon_emerald'
        >>> parsed.version
        '1.0.0'
    """
    match = ISLAND_PATTERN.match(filename)
    if not match:
        raise FilenameError(f"Invalid Island filename: {filename}")

    return ParsedIslandFilename(
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
