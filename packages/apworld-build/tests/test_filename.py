# SPDX-License-Identifier: MIT
"""Tests for filename conventions module."""

import pytest

from apworld_build.filename import (
    FilenameError,
    PlatformTag,
    UNIVERSAL_TAG,
    build_apworld_filename,
    build_sdist_filename,
    is_pure_python_tag,
    normalize_name,
    normalize_version,
    parse_apworld_filename,
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


class TestBuildApworldFilename:
    """Tests for build_apworld_filename function."""

    def test_universal_filename(self):
        filename = build_apworld_filename("pokemon-emerald", "1.0.0")
        assert filename == "pokemon_emerald-1.0.0-py3-none-any.apworld"

    def test_prerelease_version(self):
        filename = build_apworld_filename("my-game", "2.0.0-alpha.1")
        assert filename == "my_game-2.0.0_alpha.1-py3-none-any.apworld"

    def test_custom_platform_tag(self):
        tag = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
        filename = build_apworld_filename("my-game", "1.0.0", tag)
        assert filename == "my_game-1.0.0-cp311-cp311-win_amd64.apworld"


class TestBuildSdistFilename:
    """Tests for build_sdist_filename function."""

    def test_simple_filename(self):
        filename = build_sdist_filename("pokemon-emerald", "1.0.0")
        assert filename == "pokemon_emerald-1.0.0.tar.gz"

    def test_prerelease_version(self):
        filename = build_sdist_filename("my-game", "2.0.0-alpha.1")
        assert filename == "my_game-2.0.0_alpha.1.tar.gz"


class TestParseApworldFilename:
    """Tests for parse_apworld_filename function."""

    def test_parse_universal(self):
        parsed = parse_apworld_filename("pokemon_emerald-1.0.0-py3-none-any.apworld")
        assert parsed.name == "pokemon_emerald"
        assert parsed.version == "1.0.0"
        assert parsed.tag.python == "py3"
        assert parsed.tag.abi == "none"
        assert parsed.tag.platform == "any"

    def test_parse_platform_specific(self):
        parsed = parse_apworld_filename("my_game-2.0.0-cp311-cp311-win_amd64.apworld")
        assert parsed.name == "my_game"
        assert parsed.version == "2.0.0"
        assert parsed.tag.platform == "win_amd64"

    def test_parse_invalid_raises(self):
        with pytest.raises(FilenameError, match="Invalid APWorld filename"):
            parse_apworld_filename("invalid.apworld")


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
