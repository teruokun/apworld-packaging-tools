# SPDX-License-Identifier: MIT
"""Unit tests for semantic version parsing."""

import pytest

from apworld_version import (
    Version,
    parse_version,
    is_valid_semver,
    InvalidVersionError,
)


class TestParseVersion:
    """Tests for parse_version function."""

    def test_basic_version(self):
        """Test parsing basic MAJOR.MINOR.PATCH version."""
        v = parse_version("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.prerelease is None
        assert v.build is None

    def test_version_with_zeros(self):
        """Test parsing version with zero components."""
        v = parse_version("0.0.0")
        assert v.major == 0
        assert v.minor == 0
        assert v.patch == 0

    def test_large_version_numbers(self):
        """Test parsing large version numbers."""
        v = parse_version("999.888.777")
        assert v.major == 999
        assert v.minor == 888
        assert v.patch == 777

    def test_prerelease_alpha(self):
        """Test parsing alpha pre-release."""
        v = parse_version("1.0.0-alpha")
        assert v.prerelease == "alpha"
        assert v.is_prerelease is True

    def test_prerelease_alpha_numbered(self):
        """Test parsing numbered alpha pre-release."""
        v = parse_version("1.0.0-alpha.1")
        assert v.prerelease == "alpha.1"

    def test_prerelease_beta(self):
        """Test parsing beta pre-release."""
        v = parse_version("2.0.0-beta.2")
        assert v.prerelease == "beta.2"

    def test_prerelease_rc(self):
        """Test parsing release candidate."""
        v = parse_version("3.0.0-rc.1")
        assert v.prerelease == "rc.1"

    def test_build_metadata(self):
        """Test parsing build metadata."""
        v = parse_version("1.0.0+build.123")
        assert v.build == "build.123"
        assert v.prerelease is None

    def test_prerelease_and_build(self):
        """Test parsing both pre-release and build metadata."""
        v = parse_version("1.0.0-alpha.1+build.456")
        assert v.prerelease == "alpha.1"
        assert v.build == "build.456"

    def test_complex_prerelease(self):
        """Test parsing complex pre-release identifiers."""
        v = parse_version("1.0.0-alpha.1.beta.2")
        assert v.prerelease == "alpha.1.beta.2"

    def test_numeric_prerelease(self):
        """Test parsing numeric-only pre-release."""
        v = parse_version("1.0.0-0.3.7")
        assert v.prerelease == "0.3.7"

    def test_version_str(self):
        """Test Version string representation."""
        v = parse_version("1.2.3-alpha.1+build")
        assert str(v) == "1.2.3-alpha.1+build"

    def test_base_version(self):
        """Test base_version property."""
        v = parse_version("1.2.3-alpha.1+build")
        assert v.base_version == "1.2.3"


class TestInvalidVersions:
    """Tests for invalid version strings."""

    def test_empty_string(self):
        """Test that empty string raises error."""
        with pytest.raises(InvalidVersionError):
            parse_version("")

    def test_whitespace_only(self):
        """Test that whitespace-only string raises error."""
        with pytest.raises(InvalidVersionError):
            parse_version("   ")

    def test_missing_patch(self):
        """Test that missing patch version raises error."""
        with pytest.raises(InvalidVersionError):
            parse_version("1.0")

    def test_missing_minor(self):
        """Test that missing minor version raises error."""
        with pytest.raises(InvalidVersionError):
            parse_version("1")

    def test_leading_zeros(self):
        """Test that leading zeros in numeric parts raise error."""
        with pytest.raises(InvalidVersionError):
            parse_version("01.0.0")

    def test_negative_numbers(self):
        """Test that negative numbers raise error."""
        with pytest.raises(InvalidVersionError):
            parse_version("-1.0.0")

    def test_non_numeric_version(self):
        """Test that non-numeric version parts raise error."""
        with pytest.raises(InvalidVersionError):
            parse_version("a.b.c")

    def test_extra_parts(self):
        """Test that extra version parts raise error."""
        with pytest.raises(InvalidVersionError):
            parse_version("1.2.3.4")

    def test_invalid_prerelease_leading_zero(self):
        """Test that leading zeros in numeric prerelease raise error."""
        with pytest.raises(InvalidVersionError):
            parse_version("1.0.0-01")

    def test_non_string_input(self):
        """Test that non-string input raises error."""
        with pytest.raises(InvalidVersionError):
            parse_version(123)  # type: ignore

    def test_none_input(self):
        """Test that None input raises error."""
        with pytest.raises(InvalidVersionError):
            parse_version(None)  # type: ignore


class TestIsValidSemver:
    """Tests for is_valid_semver function."""

    def test_valid_basic(self):
        """Test valid basic version."""
        assert is_valid_semver("1.0.0") is True

    def test_valid_prerelease(self):
        """Test valid pre-release version."""
        assert is_valid_semver("1.0.0-alpha") is True

    def test_valid_build(self):
        """Test valid build metadata."""
        assert is_valid_semver("1.0.0+build") is True

    def test_valid_full(self):
        """Test valid full version."""
        assert is_valid_semver("1.0.0-alpha.1+build.123") is True

    def test_invalid_missing_patch(self):
        """Test invalid version missing patch."""
        assert is_valid_semver("1.0") is False

    def test_invalid_empty(self):
        """Test invalid empty string."""
        assert is_valid_semver("") is False

    def test_invalid_non_string(self):
        """Test invalid non-string input."""
        assert is_valid_semver(123) is False  # type: ignore

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed."""
        assert is_valid_semver("  1.0.0  ") is True


class TestVersionEquality:
    """Tests for Version equality and hashing."""

    def test_equal_versions(self):
        """Test that equal versions are equal."""
        v1 = parse_version("1.0.0")
        v2 = parse_version("1.0.0")
        assert v1 == v2

    def test_different_versions(self):
        """Test that different versions are not equal."""
        v1 = parse_version("1.0.0")
        v2 = parse_version("2.0.0")
        assert v1 != v2

    def test_hashable(self):
        """Test that versions are hashable."""
        v = parse_version("1.0.0")
        assert hash(v) is not None
        # Can be used in sets
        s = {v}
        assert v in s

    def test_frozen(self):
        """Test that Version is immutable."""
        v = parse_version("1.0.0")
        with pytest.raises(AttributeError):
            v.major = 2  # type: ignore
