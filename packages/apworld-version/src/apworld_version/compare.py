# SPDX-License-Identifier: MIT
"""Version comparison following PEP 440 ordering semantics.

Pre-release ordering: alpha < beta < rc < release
Build metadata is ignored in comparisons per SemVer spec.
"""

from __future__ import annotations

from typing import Union

from .semver import Version, parse_version, InvalidVersionError

# Pre-release type ordering (lower = earlier in release cycle)
_PRERELEASE_ORDER = {
    "alpha": 0,
    "a": 0,
    "beta": 1,
    "b": 1,
    "rc": 2,
    "c": 2,
    "preview": 0,
    "pre": 0,
}


def _parse_prerelease_part(part: str) -> tuple[int, int]:
    """Parse a single pre-release identifier part.

    Returns a tuple of (type_order, numeric_value) for comparison.
    Type order determines alpha < beta < rc ordering.
    Numeric value handles alpha.1 < alpha.2.
    """
    # Try to parse as pure number
    if part.isdigit():
        return (3, int(part))  # Numbers sort after named pre-releases

    # Check for named pre-release types
    part_lower = part.lower()
    for prefix, order in _PRERELEASE_ORDER.items():
        if part_lower == prefix:
            return (order, 0)
        if part_lower.startswith(prefix):
            # Handle cases like "alpha1" without separator
            suffix = part_lower[len(prefix) :]
            if suffix.isdigit():
                return (order, int(suffix))

    # Unknown identifier - sort alphabetically after known types
    return (4, 0)


def _compare_prerelease(pre1: str | None, pre2: str | None) -> int:
    """Compare two pre-release strings.

    Returns:
        -1 if pre1 < pre2
        0 if pre1 == pre2
        1 if pre1 > pre2

    Per SemVer: a version without pre-release has higher precedence
    than one with pre-release (1.0.0 > 1.0.0-alpha).
    """
    # No pre-release > any pre-release
    if pre1 is None and pre2 is None:
        return 0
    if pre1 is None:
        return 1  # Release > pre-release
    if pre2 is None:
        return -1  # Pre-release < release

    # Split into parts and compare
    parts1 = pre1.split(".")
    parts2 = pre2.split(".")

    for p1, p2 in zip(parts1, parts2):
        # Try numeric comparison first
        is_num1 = p1.isdigit()
        is_num2 = p2.isdigit()

        if is_num1 and is_num2:
            n1, n2 = int(p1), int(p2)
            if n1 != n2:
                return -1 if n1 < n2 else 1
        elif is_num1:
            # Numeric < alphabetic per SemVer
            return -1
        elif is_num2:
            return 1
        else:
            # Both alphabetic - check for known pre-release types
            order1 = _parse_prerelease_part(p1)
            order2 = _parse_prerelease_part(p2)
            if order1 != order2:
                return -1 if order1 < order2 else 1

    # All compared parts equal - longer pre-release has higher precedence
    if len(parts1) != len(parts2):
        return -1 if len(parts1) < len(parts2) else 1

    return 0


def compare_versions(version1: Union[str, Version], version2: Union[str, Version]) -> int:
    """Compare two semantic versions following PEP 440 ordering.

    Args:
        version1: First version (string or Version object)
        version2: Second version (string or Version object)

    Returns:
        -1 if version1 < version2
        0 if version1 == version2
        1 if version1 > version2

    Raises:
        InvalidVersionError: If either version string is invalid

    Note:
        Build metadata is ignored in comparisons per SemVer specification.
        Pre-release ordering: alpha < beta < rc < release

    Examples:
        >>> compare_versions("1.0.0", "2.0.0")
        -1
        >>> compare_versions("1.0.0", "1.0.0")
        0
        >>> compare_versions("2.0.0", "1.0.0")
        1
        >>> compare_versions("1.0.0-alpha", "1.0.0-beta")
        -1
        >>> compare_versions("1.0.0-rc.1", "1.0.0")
        -1
    """
    # Parse if strings
    v1 = parse_version(version1) if isinstance(version1, str) else version1
    v2 = parse_version(version2) if isinstance(version2, str) else version2

    # Compare major.minor.patch
    for attr in ("major", "minor", "patch"):
        val1 = getattr(v1, attr)
        val2 = getattr(v2, attr)
        if val1 != val2:
            return -1 if val1 < val2 else 1

    # Compare pre-release (build metadata is ignored)
    return _compare_prerelease(v1.prerelease, v2.prerelease)


def version_key(version: Union[str, Version]) -> tuple:
    """Return a sort key for a version, suitable for sorting.

    Args:
        version: Version string or Version object

    Returns:
        A tuple that can be used for sorting versions

    Examples:
        >>> sorted(["1.0.0", "2.0.0", "1.0.0-alpha"], key=version_key)
        ['1.0.0-alpha', '1.0.0', '2.0.0']
    """
    v = parse_version(version) if isinstance(version, str) else version

    # Pre-release key: None becomes (1,) to sort after pre-releases
    # Pre-release strings become (0, parsed_parts...)
    if v.prerelease is None:
        prerelease_key: tuple = (1,)
    else:
        parts = []
        for part in v.prerelease.split("."):
            if part.isdigit():
                parts.append((1, int(part)))
            else:
                parsed = _parse_prerelease_part(part)
                parts.append((0, parsed))
        prerelease_key = (0, tuple(parts))

    return (v.major, v.minor, v.patch, prerelease_key)
