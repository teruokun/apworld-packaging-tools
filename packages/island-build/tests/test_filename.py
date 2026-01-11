# SPDX-License-Identifier: MIT
"""Tests for filename conventions module."""

import pytest

from island_build.filename import (
    FilenameError,
    PlatformTag,
    UNIVERSAL_TAG,
    build_island_filename,
    build_sdist_filename,
    is_pure_python_tag,
    normalize_name,
    normalize_version,
    parse_island_filename,
    parse_sdist_filename,
)


class TestNormalizeName:
    """Tests for normalize_name function."""

    def test_lowercase_conversion(self):
        assert normalize_name("Pokemon-Emerald") == "pokemon_emerald"

    def test_hyphen_to_underscore(self):
        assert normalize_name("my-game-world") == "my_game_world"

    def test_period_to_underscore(self):
        assert normalize_name("my.game.world") == "my_game_world"

    def test_space_to_underscore(self):
        assert normalize_name("my game world") == "my_game_world"

    def test_collapse_multiple_underscores(self):
        assert normalize_name("my--game__world") == "my_game_world"

    def test_strip_leading_trailing_underscores(self):
        assert normalize_name("-my-game-") == "my_game"

    def test_empty_name_raises(self):
        with pytest.raises(FilenameError, match="cannot be empty"):
            normalize_name("")

    def test_only_separators_raises(self):
        with pytest.raises(FilenameError, match="Invalid package name"):
            normalize_name("---")


class TestNormalizeVersion:
    """Tests for normalize_version function."""

    def test_simple_version(self):
        assert normalize_version("1.0.0") == "1.0.0"

    def test_prerelease_hyphen_to_underscore(self):
        assert normalize_version("1.0.0-alpha.1") == "1.0.0_alpha.1"

    def test_build_metadata_preserved(self):
        assert normalize_version("2.0.0+build.123") == "2.0.0+build.123"

    def test_empty_version_raises(self):
        with pytest.raises(FilenameError, match="cannot be empty"):
            normalize_version("")


class TestPlatformTag:
    """Tests for PlatformTag class."""

    def test_universal_tag(self):
        tag = PlatformTag.universal()
        assert tag.python == "py3"
        assert tag.abi == "none"
        assert tag.platform == "any"

    def test_str_representation(self):
        tag = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
        assert str(tag) == "cp311-cp311-win_amd64"

    def test_from_string(self):
        tag = PlatformTag.from_string("py3-none-any")
        assert tag.python == "py3"
        assert tag.abi == "none"
        assert tag.platform == "any"

    def test_from_string_invalid(self):
        with pytest.raises(FilenameError, match="Invalid platform tag"):
            PlatformTag.from_string("invalid")


class TestBuildIslandFilename:
    """Tests for build_island_filename function."""

    def test_universal_filename(self):
        filename = build_island_filename("pokemon-emerald", "1.0.0")
        assert filename == "pokemon_emerald-1.0.0-py3-none-any.island"

    def test_prerelease_version(self):
        filename = build_island_filename("my-game", "2.0.0-alpha.1")
        assert filename == "my_game-2.0.0_alpha.1-py3-none-any.island"

    def test_custom_platform_tag(self):
        tag = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
        filename = build_island_filename("my-game", "1.0.0", tag)
        assert filename == "my_game-1.0.0-cp311-cp311-win_amd64.island"


class TestBuildSdistFilename:
    """Tests for build_sdist_filename function."""

    def test_simple_filename(self):
        filename = build_sdist_filename("pokemon-emerald", "1.0.0")
        assert filename == "pokemon_emerald-1.0.0.tar.gz"

    def test_prerelease_version(self):
        filename = build_sdist_filename("my-game", "2.0.0-alpha.1")
        assert filename == "my_game-2.0.0_alpha.1.tar.gz"


class TestParseIslandFilename:
    """Tests for parse_island_filename function."""

    def test_parse_universal(self):
        parsed = parse_island_filename("pokemon_emerald-1.0.0-py3-none-any.island")
        assert parsed.name == "pokemon_emerald"
        assert parsed.version == "1.0.0"
        assert parsed.tag.python == "py3"
        assert parsed.tag.abi == "none"
        assert parsed.tag.platform == "any"

    def test_parse_platform_specific(self):
        parsed = parse_island_filename("my_game-2.0.0-cp311-cp311-win_amd64.island")
        assert parsed.name == "my_game"
        assert parsed.version == "2.0.0"
        assert parsed.tag.platform == "win_amd64"

    def test_parse_invalid_raises(self):
        with pytest.raises(FilenameError, match="Invalid Island filename"):
            parse_island_filename("invalid.island")


class TestParseSdistFilename:
    """Tests for parse_sdist_filename function."""

    def test_parse_simple(self):
        parsed = parse_sdist_filename("pokemon_emerald-1.0.0.tar.gz")
        assert parsed.name == "pokemon_emerald"
        assert parsed.version == "1.0.0"

    def test_parse_invalid_raises(self):
        with pytest.raises(FilenameError, match="Invalid sdist filename"):
            parse_sdist_filename("invalid.zip")


class TestIsPurePythonTag:
    """Tests for is_pure_python_tag function."""

    def test_universal_is_pure(self):
        assert is_pure_python_tag(UNIVERSAL_TAG) is True

    def test_platform_specific_not_pure(self):
        tag = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
        assert is_pure_python_tag(tag) is False

    def test_py3_none_any_is_pure(self):
        tag = PlatformTag(python="py3", abi="none", platform="any")
        assert is_pure_python_tag(tag) is True


# =============================================================================
# Property-Based Tests using Hypothesis
# =============================================================================

from hypothesis import given, strategies as st, settings, assume

from island_build.filename import IslandFilename


# Strategies for generating valid components
# Valid distribution names: start with alphanumeric, followed by alphanumeric or underscore
valid_distribution_names = st.from_regex(r"[a-z][a-z0-9_]{0,30}", fullmatch=True)

# Valid versions: simple semver-like versions
valid_versions = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)

# Valid python tags: py3, cp311, cp312, etc.
valid_python_tags = st.sampled_from(["py3", "cp311", "cp312", "cp313"])

# Valid ABI tags: none, cp311, abi3, etc.
valid_abi_tags = st.sampled_from(["none", "cp311", "cp312", "abi3"])

# Valid platform tags: any, win_amd64, linux_x86_64, etc.
valid_platform_tags = st.sampled_from(
    [
        "any",
        "win_amd64",
        "win_arm64",
        "macosx_11_0_x86_64",
        "macosx_11_0_arm64",
        "manylinux_2_17_x86_64",
        "manylinux_2_17_aarch64",
        "linux_x86_64",
    ]
)

# Optional build tags: None or a numeric string
valid_build_tags = st.one_of(st.none(), st.integers(min_value=1, max_value=999).map(str))


@st.composite
def valid_platform_tag_objects(draw):
    """Generate valid PlatformTag objects."""
    return PlatformTag(
        python=draw(valid_python_tags),
        abi=draw(valid_abi_tags),
        platform=draw(valid_platform_tags),
    )


@st.composite
def valid_island_filenames(draw):
    """Generate valid IslandFilename objects."""
    return IslandFilename(
        distribution=draw(valid_distribution_names),
        version=draw(valid_versions),
        build_tag=draw(valid_build_tags),
        platform_tag=draw(valid_platform_tag_objects()),
    )


class TestIslandFilenamePropertyBased:
    """Property-based tests for IslandFilename.

    Feature: island-format-migration, Property 1: Island filename format compliance
    Validates: Requirements 1.1, 2.2, 5.1, 5.2, 5.3
    """

    @given(island_filename=valid_island_filenames())
    @settings(max_examples=100)
    def test_filename_ends_with_island_extension(self, island_filename: IslandFilename):
        """
        Property 1: Island filename format compliance - extension check

        *For any* valid island package configuration, the built package filename
        SHALL end with the `.island` extension.

        **Validates: Requirements 1.1**
        """
        filename = str(island_filename)
        assert filename.endswith(".island"), f"Filename {filename} should end with .island"

    @given(island_filename=valid_island_filenames())
    @settings(max_examples=100)
    def test_filename_contains_platform_tag(self, island_filename: IslandFilename):
        """
        Property 1: Island filename format compliance - platform tag check

        *For any* valid island package configuration, the filename SHALL include
        Python version tag, ABI tag, and platform tag.

        **Validates: Requirements 2.2, 5.1, 5.2, 5.3**
        """
        filename = str(island_filename)
        platform_tag = island_filename.platform_tag

        # The filename should contain the platform tag components
        assert (
            platform_tag.python in filename
        ), f"Python tag {platform_tag.python} not in {filename}"
        assert platform_tag.abi in filename, f"ABI tag {platform_tag.abi} not in {filename}"
        assert (
            platform_tag.platform in filename
        ), f"Platform tag {platform_tag.platform} not in {filename}"

    @given(island_filename=valid_island_filenames())
    @settings(max_examples=100)
    def test_filename_round_trip(self, island_filename: IslandFilename):
        """
        Property 1: Island filename format compliance - round trip

        *For any* valid IslandFilename, converting to string and parsing back
        SHALL produce an equivalent IslandFilename.

        **Validates: Requirements 1.1, 2.2**
        """
        filename = str(island_filename)
        parsed = IslandFilename.parse(filename)

        assert parsed.distribution == island_filename.distribution
        assert parsed.version == island_filename.version
        assert parsed.build_tag == island_filename.build_tag
        assert parsed.platform_tag.python == island_filename.platform_tag.python
        assert parsed.platform_tag.abi == island_filename.platform_tag.abi
        assert parsed.platform_tag.platform == island_filename.platform_tag.platform

    @given(island_filename=valid_island_filenames())
    @settings(max_examples=100)
    def test_filename_matches_expected_pattern(self, island_filename: IslandFilename):
        """
        Property 1: Island filename format compliance - pattern match

        *For any* valid island package configuration, the built package filename
        SHALL match the pattern:
        {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.island

        **Validates: Requirements 1.1, 2.2, 5.1, 5.2, 5.3**
        """
        import re

        filename = str(island_filename)

        # Pattern with optional build tag
        pattern = re.compile(
            r"^[a-z][a-z0-9_]*"  # distribution
            r"-[0-9]+\.[0-9]+\.[0-9]+"  # version
            r"(?:-\d+)?"  # optional build tag
            r"-[a-z0-9]+"  # python tag
            r"-[a-z0-9_]+"  # abi tag
            r"-[a-z0-9_]+"  # platform tag
            r"\.island$"  # extension
        )

        assert pattern.match(filename), f"Filename {filename} doesn't match expected pattern"


class TestPlatformTagPropertyBased:
    """Property-based tests for PlatformTag.

    Feature: island-format-migration, Property 1: Island filename format compliance
    Validates: Requirements 5.1, 5.2, 5.3
    """

    @given(platform_tag=valid_platform_tag_objects())
    @settings(max_examples=100)
    def test_platform_tag_round_trip(self, platform_tag: PlatformTag):
        """
        Property: Platform tag round trip

        *For any* valid PlatformTag, converting to string and parsing back
        SHALL produce an equivalent PlatformTag.

        **Validates: Requirements 5.1, 5.2, 5.3**
        """
        tag_string = str(platform_tag)
        parsed = PlatformTag.parse(tag_string)

        assert parsed.python == platform_tag.python
        assert parsed.abi == platform_tag.abi
        assert parsed.platform == platform_tag.platform

    @given(platform_tag=valid_platform_tag_objects())
    @settings(max_examples=100)
    def test_platform_tag_string_format(self, platform_tag: PlatformTag):
        """
        Property: Platform tag string format

        *For any* valid PlatformTag, the string representation SHALL be
        in the format {python}-{abi}-{platform}.

        **Validates: Requirements 5.1, 5.2, 5.3**
        """
        tag_string = str(platform_tag)
        parts = tag_string.split("-")

        assert len(parts) == 3, f"Platform tag {tag_string} should have 3 parts"
        assert parts[0] == platform_tag.python
        assert parts[1] == platform_tag.abi
        assert parts[2] == platform_tag.platform


class TestPurePythonTag:
    """Tests for pure_python class method."""

    def test_pure_python_returns_universal_tag(self):
        """Test that pure_python() returns the same as universal()."""
        pure = PlatformTag.pure_python()
        universal = PlatformTag.universal()

        assert pure.python == universal.python
        assert pure.abi == universal.abi
        assert pure.platform == universal.platform

    def test_pure_python_is_py3_none_any(self):
        """Test that pure_python() returns py3-none-any."""
        tag = PlatformTag.pure_python()
        assert str(tag) == "py3-none-any"


class TestParseMethod:
    """Tests for parse class method."""

    def test_parse_is_alias_for_from_string(self):
        """Test that parse() is an alias for from_string()."""
        tag_string = "cp311-cp311-win_amd64"
        from_string_result = PlatformTag.from_string(tag_string)
        parse_result = PlatformTag.parse(tag_string)

        assert from_string_result == parse_result


class TestIslandFilenameUnit:
    """Unit tests for IslandFilename class."""

    def test_str_without_build_tag(self):
        """Test __str__ without build tag."""
        fn = IslandFilename(
            distribution="my_game",
            version="1.0.0",
            build_tag=None,
            platform_tag=PlatformTag.pure_python(),
        )
        assert str(fn) == "my_game-1.0.0-py3-none-any.island"

    def test_str_with_build_tag(self):
        """Test __str__ with build tag."""
        fn = IslandFilename(
            distribution="my_game",
            version="1.0.0",
            build_tag="1",
            platform_tag=PlatformTag.pure_python(),
        )
        assert str(fn) == "my_game-1.0.0-1-py3-none-any.island"

    def test_parse_without_build_tag(self):
        """Test parse without build tag."""
        fn = IslandFilename.parse("pokemon_emerald-2.1.0-py3-none-any.island")
        assert fn.distribution == "pokemon_emerald"
        assert fn.version == "2.1.0"
        assert fn.build_tag is None
        assert fn.platform_tag.python == "py3"
        assert fn.platform_tag.abi == "none"
        assert fn.platform_tag.platform == "any"

    def test_parse_with_build_tag(self):
        """Test parse with build tag."""
        fn = IslandFilename.parse("complex_world-3.0.0-1-py3-none-linux_x86_64.island")
        assert fn.distribution == "complex_world"
        assert fn.version == "3.0.0"
        assert fn.build_tag == "1"
        assert fn.platform_tag.platform == "linux_x86_64"

    def test_parse_platform_specific(self):
        """Test parse with platform-specific tag."""
        fn = IslandFilename.parse("my_game-1.0.0-cp311-cp311-macosx_11_0_arm64.island")
        assert fn.distribution == "my_game"
        assert fn.version == "1.0.0"
        assert fn.build_tag is None
        assert fn.platform_tag.python == "cp311"
        assert fn.platform_tag.abi == "cp311"
        assert fn.platform_tag.platform == "macosx_11_0_arm64"

    def test_parse_invalid_raises(self):
        """Test parse with invalid filename raises error."""
        with pytest.raises(FilenameError, match="Invalid Island filename"):
            IslandFilename.parse("invalid.island")

    def test_from_parts_normalizes_name(self):
        """Test from_parts normalizes the name."""
        fn = IslandFilename.from_parts("Pokemon-Emerald", "1.0.0")
        assert fn.distribution == "pokemon_emerald"

    def test_from_parts_normalizes_version(self):
        """Test from_parts normalizes the version."""
        fn = IslandFilename.from_parts("my_game", "1.0.0-alpha")
        assert fn.version == "1.0.0_alpha"

    def test_from_parts_with_build_tag(self):
        """Test from_parts with build tag."""
        fn = IslandFilename.from_parts("my_game", "1.0.0", build_tag="2")
        assert fn.build_tag == "2"

    def test_from_parts_with_platform_tag(self):
        """Test from_parts with custom platform tag."""
        tag = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
        fn = IslandFilename.from_parts("my_game", "1.0.0", platform_tag=tag)
        assert fn.platform_tag == tag
