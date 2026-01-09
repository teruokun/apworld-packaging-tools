# SPDX-License-Identifier: MIT
"""Unit tests for version comparison."""

import pytest

from apworld_version import (
    Version,
    parse_version,
    compare_versions,
    version_key,
)


class TestCompareVersions:
    """Tests for compare_versions function."""

    def test_equal_versions(self):
        """Test that equal versions compare as equal."""
        assert compare_versions("1.0.0", "1.0.0") == 0

    def test_major_difference(self):
        """Test comparison with different major versions."""
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("2.0.0", "1.0.0") == 1

    def test_minor_difference(self):
        """Test comparison with different minor versions."""
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.1.0", "1.0.0") == 1

    def test_patch_difference(self):
        """Test comparison with different patch versions."""
        assert compare_versions("1.0.0", "1.0.1") == -1
        assert compare_versions("1.0.1", "1.0.0") == 1

    def test_prerelease_vs_release(self):
        """Test that pre-release is less than release."""
        assert compare_versions("1.0.0-alpha", "1.0.0") == -1
        assert compare_versions("1.0.0", "1.0.0-alpha") == 1

    def test_alpha_vs_beta(self):
        """Test that alpha < beta."""
        assert compare_versions("1.0.0-alpha", "1.0.0-beta") == -1
        assert compare_versions("1.0.0-beta", "1.0.0-alpha") == 1

    def test_beta_vs_rc(self):
        """Test that beta < rc."""
        assert compare_versions("1.0.0-beta", "1.0.0-rc") == -1
        assert compare_versions("1.0.0-rc", "1.0.0-beta") == 1

    def test_rc_vs_release(self):
        """Test that rc < release."""
        assert compare_versions("1.0.0-rc", "1.0.0") == -1
        assert compare_versions("1.0.0", "1.0.0-rc") == 1

    def test_numbered_prerelease(self):
        """Test comparison of numbered pre-releases."""
        assert compare_versions("1.0.0-alpha.1", "1.0.0-alpha.2") == -1
        assert compare_versions("1.0.0-alpha.2", "1.0.0-alpha.1") == 1
        assert compare_versions("1.0.0-alpha.1", "1.0.0-alpha.1") == 0

    def test_build_metadata_ignored(self):
        """Test that build metadata is ignored in comparison."""
        assert compare_versions("1.0.0+build1", "1.0.0+build2") == 0
        assert compare_versions("1.0.0+build", "1.0.0") == 0

    def test_version_objects(self):
        """Test comparison with Version objects."""
        v1 = parse_version("1.0.0")
        v2 = parse_version("2.0.0")
        assert compare_versions(v1, v2) == -1

    def test_mixed_string_and_version(self):
        """Test comparison with mixed string and Version."""
        v = parse_version("1.0.0")
        assert compare_versions(v, "2.0.0") == -1
        assert compare_versions("1.0.0", v) == 0


class TestPrereleaseOrdering:
    """Tests for pre-release ordering edge cases."""

    def test_full_prerelease_chain(self):
        """Test full pre-release ordering chain."""
        versions = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-beta",
            "1.0.0-beta.1",
            "1.0.0-rc",
            "1.0.0-rc.1",
            "1.0.0",
        ]
        for i in range(len(versions) - 1):
            assert (
                compare_versions(versions[i], versions[i + 1]) == -1
            ), f"{versions[i]} should be < {versions[i + 1]}"

    def test_numeric_prerelease_parts(self):
        """Test numeric pre-release parts comparison."""
        assert compare_versions("1.0.0-1", "1.0.0-2") == -1
        assert compare_versions("1.0.0-10", "1.0.0-2") == 1  # Numeric comparison

    def test_alpha_shorthand(self):
        """Test 'a' as shorthand for alpha."""
        # Both should be treated as alpha-level
        assert compare_versions("1.0.0-a", "1.0.0-beta") == -1

    def test_beta_shorthand(self):
        """Test 'b' as shorthand for beta."""
        assert compare_versions("1.0.0-b", "1.0.0-rc") == -1


class TestVersionKey:
    """Tests for version_key function."""

    def test_sorting_basic(self):
        """Test sorting basic versions."""
        versions = ["2.0.0", "1.0.0", "1.1.0", "1.0.1"]
        sorted_versions = sorted(versions, key=version_key)
        assert sorted_versions == ["1.0.0", "1.0.1", "1.1.0", "2.0.0"]

    def test_sorting_with_prerelease(self):
        """Test sorting versions with pre-releases."""
        versions = ["1.0.0", "1.0.0-alpha", "1.0.0-beta", "1.0.0-rc"]
        sorted_versions = sorted(versions, key=version_key)
        assert sorted_versions == ["1.0.0-alpha", "1.0.0-beta", "1.0.0-rc", "1.0.0"]

    def test_sorting_mixed(self):
        """Test sorting mixed versions."""
        versions = [
            "2.0.0",
            "1.0.0-alpha",
            "1.0.0",
            "1.1.0-beta",
            "1.0.0-rc",
        ]
        sorted_versions = sorted(versions, key=version_key)
        assert sorted_versions == [
            "1.0.0-alpha",
            "1.0.0-rc",
            "1.0.0",
            "1.1.0-beta",
            "2.0.0",
        ]

    def test_sorting_version_objects(self):
        """Test sorting Version objects."""
        versions = [parse_version("2.0.0"), parse_version("1.0.0")]
        sorted_versions = sorted(versions, key=version_key)
        assert sorted_versions[0].major == 1
        assert sorted_versions[1].major == 2


class TestTransitivity:
    """Tests for comparison transitivity."""

    def test_transitivity(self):
        """Test that comparison is transitive: if a < b and b < c, then a < c."""
        a = "1.0.0-alpha"
        b = "1.0.0-beta"
        c = "1.0.0"

        assert compare_versions(a, b) == -1
        assert compare_versions(b, c) == -1
        assert compare_versions(a, c) == -1

    def test_antisymmetry(self):
        """Test that comparison is antisymmetric: if a < b, then b > a."""
        a = "1.0.0"
        b = "2.0.0"

        assert compare_versions(a, b) == -1
        assert compare_versions(b, a) == 1

    def test_reflexivity(self):
        """Test that comparison is reflexive: a == a."""
        versions = ["1.0.0", "1.0.0-alpha", "1.0.0+build"]
        for v in versions:
            assert compare_versions(v, v) == 0
