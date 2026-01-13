# SPDX-License-Identifier: MIT
"""Platform tag detection and inheritance for Island packages.

This module provides utilities for detecting platform-specific packages
and computing the most restrictive platform tag from vendored dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Native extension file patterns by platform
NATIVE_EXTENSION_PATTERNS = frozenset(
    {
        ".so",  # Linux/Unix shared objects
        ".dll",  # Windows dynamic link libraries
        ".dylib",  # macOS dynamic libraries
        ".pyd",  # Windows Python extension modules
    }
)


@dataclass(frozen=True)
class PlatformTag:
    """A PEP 425 platform tag.

    Attributes:
        python_tag: Python implementation and version (e.g., "py3", "cp311")
        abi_tag: ABI tag (e.g., "none", "cp311", "abi3")
        platform_tag: Platform tag (e.g., "any", "linux_x86_64", "macosx_11_0_arm64")
    """

    python_tag: str
    abi_tag: str
    platform_tag: str

    @property
    def is_pure_python(self) -> bool:
        """Check if this tag represents a pure Python package."""
        return self.platform_tag == "any" and self.abi_tag == "none"

    def __str__(self) -> str:
        """Return the full tag string."""
        return f"{self.python_tag}-{self.abi_tag}-{self.platform_tag}"

    @classmethod
    def pure_python(cls) -> "PlatformTag":
        """Create a pure Python platform tag (py3-none-any)."""
        return cls(python_tag="py3", abi_tag="none", platform_tag="any")

    @classmethod
    def from_string(cls, tag_string: str) -> "PlatformTag":
        """Parse a platform tag from a string.

        Args:
            tag_string: Tag string in format "python-abi-platform"

        Returns:
            PlatformTag instance

        Raises:
            ValueError: If the tag string is invalid
        """
        parts = tag_string.split("-")
        if len(parts) < 3:
            raise ValueError(f"Invalid platform tag: {tag_string}")

        # Handle platform tags with hyphens (e.g., macosx_11_0_arm64)
        python_tag = parts[0]
        abi_tag = parts[1]
        platform_tag = "-".join(parts[2:])

        return cls(python_tag=python_tag, abi_tag=abi_tag, platform_tag=platform_tag)


def detect_native_extensions(package_dir: Path) -> list[Path]:
    """Find all native extension files in a package directory.

    Args:
        package_dir: Directory containing the extracted package

    Returns:
        List of paths to native extension files
    """
    native_files: list[Path] = []

    if not package_dir.exists():
        return native_files

    for pattern in NATIVE_EXTENSION_PATTERNS:
        native_files.extend(package_dir.rglob(f"*{pattern}"))

    return native_files


def parse_wheel_tags(wheel_path: Path) -> list[PlatformTag]:
    """Parse platform tags from a wheel file's WHEEL metadata.

    Args:
        wheel_path: Path to the wheel file

    Returns:
        List of PlatformTag instances from the wheel
    """
    import zipfile

    tags: list[PlatformTag] = []

    try:
        with zipfile.ZipFile(wheel_path, "r") as whl:
            # Find the WHEEL file in .dist-info
            wheel_file = None
            for name in whl.namelist():
                if name.endswith("/WHEEL"):
                    wheel_file = name
                    break

            if not wheel_file:
                # Fall back to parsing from filename
                return parse_wheel_filename_tags(wheel_path.name)

            content = whl.read(wheel_file).decode("utf-8")

            for line in content.splitlines():
                if line.startswith("Tag:"):
                    tag_str = line.split(":", 1)[1].strip()
                    try:
                        tags.append(PlatformTag.from_string(tag_str))
                    except ValueError:
                        continue
    except Exception:
        # Fall back to filename parsing
        return parse_wheel_filename_tags(wheel_path.name)

    if not tags:
        # Fall back to filename parsing
        return parse_wheel_filename_tags(wheel_path.name)

    return tags


def parse_wheel_filename_tags(wheel_filename: str) -> list[PlatformTag]:
    """Parse platform tags from a wheel filename.

    Wheel filenames follow the pattern:
    {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl

    Args:
        wheel_filename: Name of the wheel file

    Returns:
        List of PlatformTag instances
    """
    # Remove .whl extension
    name = wheel_filename.rsplit(".", 1)[0]

    # Split by hyphens, but we need to handle the last 3 parts specially
    parts = name.split("-")

    if len(parts) < 5:
        # Invalid wheel filename, return pure Python as default
        return [PlatformTag.pure_python()]

    # Last three parts are python-abi-platform
    python_tag = parts[-3]
    abi_tag = parts[-2]
    platform_tag = parts[-1]

    return [PlatformTag(python_tag=python_tag, abi_tag=abi_tag, platform_tag=platform_tag)]


def detect_package_platform(
    package_dir: Path,
    wheel_path: Path | None = None,
) -> tuple[bool, list[PlatformTag]]:
    """Detect if a package is platform-specific.

    This function checks for:
    1. Native extension files (.so, .dll, .dylib, .pyd)
    2. Platform tags from the wheel file

    Args:
        package_dir: Directory containing the extracted package
        wheel_path: Optional path to the wheel file for tag extraction

    Returns:
        Tuple of (is_pure_python, platform_tags)
    """
    # Check for native extensions
    native_files = detect_native_extensions(package_dir)
    has_native = len(native_files) > 0

    # Get platform tags from wheel if available
    tags: list[PlatformTag] = []
    if wheel_path and wheel_path.exists():
        tags = parse_wheel_tags(wheel_path)

    # If no tags found, infer from native extensions
    if not tags:
        if has_native:
            # We know it's platform-specific but don't know the exact tag
            # This shouldn't happen in practice since wheels have tags
            tags = []
        else:
            tags = [PlatformTag.pure_python()]

    # Determine if pure Python
    # A package is pure Python if:
    # 1. It has no native extensions AND
    # 2. All its tags are pure Python (py3-none-any or similar)
    is_pure = not has_native and all(tag.is_pure_python for tag in tags)

    return is_pure, tags


def _get_platform_specificity(tag: PlatformTag) -> int:
    """Get a specificity score for a platform tag.

    Higher scores mean more restrictive/specific tags.

    Args:
        tag: Platform tag to score

    Returns:
        Specificity score (higher = more specific)
    """
    score = 0

    # Platform specificity
    if tag.platform_tag == "any":
        score += 0
    elif tag.platform_tag.startswith("linux"):
        score += 10
    elif tag.platform_tag.startswith("macosx"):
        score += 10
    elif tag.platform_tag.startswith("win"):
        score += 10
    else:
        score += 5  # Unknown platform

    # ABI specificity
    if tag.abi_tag == "none":
        score += 0
    elif tag.abi_tag == "abi3":
        score += 5  # Stable ABI
    else:
        score += 10  # Specific ABI (e.g., cp311)

    # Python version specificity
    if tag.python_tag.startswith("py"):
        score += 0  # Generic Python
    elif tag.python_tag.startswith("cp"):
        score += 5  # CPython specific
    else:
        score += 3  # Other implementation

    return score


def compute_most_restrictive_tag(tags: list[PlatformTag]) -> PlatformTag:
    """Compute the most restrictive compatible platform tag.

    If all tags are pure Python (py3-none-any), returns py3-none-any.
    Otherwise, returns the most specific platform tag.

    Args:
        tags: List of platform tags from vendored packages

    Returns:
        The most restrictive platform tag
    """
    if not tags:
        return PlatformTag.pure_python()

    # If all tags are pure Python, return pure Python
    if all(tag.is_pure_python for tag in tags):
        return PlatformTag.pure_python()

    # Filter to platform-specific tags
    platform_specific = [tag for tag in tags if not tag.is_pure_python]

    if not platform_specific:
        return PlatformTag.pure_python()

    # Find the most restrictive tag by specificity score
    return max(platform_specific, key=_get_platform_specificity)


def get_platform_compatibility(tags: list[PlatformTag]) -> dict[str, set[str]]:
    """Group platform tags by their target platform.

    This is useful for detecting incompatible platform combinations.

    Args:
        tags: List of platform tags

    Returns:
        Dictionary mapping platform family to set of specific platforms
    """
    platforms: dict[str, set[str]] = {
        "linux": set(),
        "macosx": set(),
        "win": set(),
        "any": set(),
        "other": set(),
    }

    for tag in tags:
        platform = tag.platform_tag
        if platform == "any":
            platforms["any"].add(platform)
        elif platform.startswith("linux"):
            platforms["linux"].add(platform)
        elif platform.startswith("macosx"):
            platforms["macosx"].add(platform)
        elif platform.startswith("win"):
            platforms["win"].add(platform)
        else:
            platforms["other"].add(platform)

    return platforms


def check_platform_compatibility(tags: list[PlatformTag]) -> tuple[bool, str | None]:
    """Check if a set of platform tags are compatible.

    Platform tags are compatible if they all target the same platform family
    (or are pure Python).

    Args:
        tags: List of platform tags to check

    Returns:
        Tuple of (is_compatible, error_message)
    """
    if not tags:
        return True, None

    # Get platform families
    compatibility = get_platform_compatibility(tags)

    # Count non-empty platform families (excluding 'any')
    non_any_platforms = [
        family for family, platforms in compatibility.items() if family != "any" and platforms
    ]

    if len(non_any_platforms) > 1:
        # Multiple platform families detected
        families = ", ".join(non_any_platforms)
        return False, f"Incompatible platform families detected: {families}"

    return True, None
