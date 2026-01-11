# SPDX-License-Identifier: MIT
"""Tests for entry point validation.

Feature: island-format-migration
Property 4: Entry point validation
Validates: Requirements 3.1, 3.2, 3.5
"""

import zipfile

import pytest
from hypothesis import given, settings, strategies as st

from island_build import (
    ENTRY_POINT_PATTERN,
    BuildConfig,
    InvalidEntryPointError,
    MissingEntryPointError,
    build_island,
    extract_entry_points_from_pyproject,
    validate_entry_point_format,
    validate_entry_points,
)
from island_build.wheel import get_dist_info_name


# =============================================================================
# Unit Tests for Entry Point Validation
# =============================================================================


class TestValidateEntryPointFormat:
    """Unit tests for validate_entry_point_format function."""

    def test_valid_simple_entry_point(self):
        """Test valid simple entry point format."""
        # Should not raise
        validate_entry_point_format("my_game", "my_game.world:MyGameWorld")

    def test_valid_nested_module(self):
        """Test valid entry point with nested module path."""
        validate_entry_point_format("game", "my_game.sub.module:WorldClass")

    def test_valid_single_module(self):
        """Test valid entry point with single module."""
        validate_entry_point_format("game", "world:GameWorld")

    def test_invalid_empty_value(self):
        """Test that empty value raises InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError) as exc_info:
            validate_entry_point_format("my_game", "")
        assert "cannot be empty" in str(exc_info.value)

    def test_invalid_no_colon(self):
        """Test that missing colon raises InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError) as exc_info:
            validate_entry_point_format("my_game", "my_game.world.MyGameWorld")
        assert "':' separator" in str(exc_info.value)

    def test_invalid_module_starts_with_number(self):
        """Test that module starting with number raises InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError) as exc_info:
            validate_entry_point_format("my_game", "123game:World")
        assert "valid Python identifiers" in str(exc_info.value)

    def test_invalid_attribute_starts_with_number(self):
        """Test that attribute starting with number raises InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError) as exc_info:
            validate_entry_point_format("my_game", "my_game:123World")
        assert "valid Python identifiers" in str(exc_info.value)

    def test_invalid_special_characters(self):
        """Test that special characters raise InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError) as exc_info:
            validate_entry_point_format("my_game", "my-game:World")
        assert "valid Python identifiers" in str(exc_info.value)


class TestValidateEntryPoints:
    """Unit tests for validate_entry_points function."""

    def test_valid_single_entry_point(self):
        """Test validation passes with single ap-island entry point."""
        entry_points = {"ap-island": {"my_game": "my_game.world:MyGameWorld"}}
        # Should not raise
        validate_entry_points(entry_points)

    def test_valid_multiple_entry_points(self):
        """Test validation passes with multiple ap-island entry points."""
        entry_points = {
            "ap-island": {
                "my_game": "my_game.world:MyGameWorld",
                "my_game_alt": "my_game.alt:AltWorld",
            }
        }
        validate_entry_points(entry_points)

    def test_valid_with_other_groups(self):
        """Test validation passes with ap-island and other entry point groups."""
        entry_points = {
            "ap-island": {"my_game": "my_game.world:MyGameWorld"},
            "console_scripts": {"my-cli": "my_game.cli:main"},
        }
        validate_entry_points(entry_points)

    def test_missing_entry_points_none(self):
        """Test that None entry points raises MissingEntryPointError."""
        with pytest.raises(MissingEntryPointError):
            validate_entry_points(None)

    def test_missing_entry_points_empty(self):
        """Test that empty entry points raises MissingEntryPointError."""
        with pytest.raises(MissingEntryPointError):
            validate_entry_points({})

    def test_missing_ap_island_group(self):
        """Test that missing ap-island group raises MissingEntryPointError."""
        entry_points = {"console_scripts": {"my-cli": "my_game.cli:main"}}
        with pytest.raises(MissingEntryPointError):
            validate_entry_points(entry_points)

    def test_empty_ap_island_group(self):
        """Test that empty ap-island group raises MissingEntryPointError."""
        entry_points = {"ap-island": {}}
        with pytest.raises(MissingEntryPointError):
            validate_entry_points(entry_points)

    def test_invalid_entry_point_format_in_group(self):
        """Test that invalid entry point format raises InvalidEntryPointError."""
        entry_points = {"ap-island": {"my_game": "invalid-format"}}
        with pytest.raises(InvalidEntryPointError):
            validate_entry_points(entry_points)


class TestExtractEntryPointsFromPyproject:
    """Unit tests for extract_entry_points_from_pyproject function."""

    def test_extract_ap_island_entry_points(self):
        """Test extracting ap-island entry points from pyproject dict."""
        pyproject = {
            "project": {
                "name": "my-game",
                "entry-points": {"ap-island": {"my_game": "my_game.world:MyGameWorld"}},
            }
        }
        result = extract_entry_points_from_pyproject(pyproject)
        assert result == {"ap-island": {"my_game": "my_game.world:MyGameWorld"}}

    def test_extract_multiple_groups(self):
        """Test extracting multiple entry point groups."""
        pyproject = {
            "project": {
                "entry-points": {
                    "ap-island": {"my_game": "my_game.world:MyGameWorld"},
                    "console_scripts": {"cli": "my_game.cli:main"},
                }
            }
        }
        result = extract_entry_points_from_pyproject(pyproject)
        assert "ap-island" in result
        assert "console_scripts" in result

    def test_extract_empty_when_missing(self):
        """Test returns empty dict when entry-points missing."""
        pyproject = {"project": {"name": "my-game"}}
        result = extract_entry_points_from_pyproject(pyproject)
        assert result == {}

    def test_extract_empty_when_no_project(self):
        """Test returns empty dict when project section missing."""
        pyproject = {"tool": {"island": {}}}
        result = extract_entry_points_from_pyproject(pyproject)
        assert result == {}


class TestEntryPointPattern:
    """Unit tests for ENTRY_POINT_PATTERN regex."""

    def test_pattern_matches_simple(self):
        """Test pattern matches simple entry point."""
        assert ENTRY_POINT_PATTERN.match("module:Class")

    def test_pattern_matches_nested(self):
        """Test pattern matches nested module path."""
        assert ENTRY_POINT_PATTERN.match("my_game.world.sub:MyClass")

    def test_pattern_matches_underscores(self):
        """Test pattern matches identifiers with underscores."""
        assert ENTRY_POINT_PATTERN.match("my_game_world:My_Game_World")

    def test_pattern_matches_numbers(self):
        """Test pattern matches identifiers with numbers (not at start)."""
        assert ENTRY_POINT_PATTERN.match("game2:World3")

    def test_pattern_rejects_hyphen(self):
        """Test pattern rejects hyphens in identifiers."""
        assert not ENTRY_POINT_PATTERN.match("my-game:World")

    def test_pattern_rejects_leading_number(self):
        """Test pattern rejects leading numbers."""
        assert not ENTRY_POINT_PATTERN.match("2game:World")

    def test_pattern_rejects_no_colon(self):
        """Test pattern rejects missing colon."""
        assert not ENTRY_POINT_PATTERN.match("my_game.World")


# =============================================================================
# Property-Based Tests using Hypothesis
# =============================================================================

# Strategies for generating valid entry point components
valid_identifiers = st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_]{0,20}", fullmatch=True)
valid_module_paths = st.lists(valid_identifiers, min_size=1, max_size=4).map(lambda x: ".".join(x))


@st.composite
def valid_entry_point_values(draw):
    """Generate valid entry point values (module.path:attribute)."""
    module_path = draw(valid_module_paths)
    attribute = draw(valid_identifiers)
    return f"{module_path}:{attribute}"


@st.composite
def valid_ap_island_entry_points(draw):
    """Generate valid ap-island entry point dictionaries."""
    num_entries = draw(st.integers(min_value=1, max_value=5))
    entries = {}
    for _ in range(num_entries):
        name = draw(valid_identifiers)
        value = draw(valid_entry_point_values())
        entries[name] = value
    return {"ap-island": entries}


@st.composite
def invalid_entry_point_values(draw):
    """Generate invalid entry point values."""
    invalid_type = draw(st.sampled_from(["no_colon", "leading_number", "hyphen", "empty"]))
    if invalid_type == "no_colon":
        return draw(valid_module_paths)  # Missing colon
    elif invalid_type == "leading_number":
        return f"123module:{draw(valid_identifiers)}"
    elif invalid_type == "hyphen":
        return f"my-game:{draw(valid_identifiers)}"
    else:
        return ""


# Strategies for package names and versions
valid_package_names = st.from_regex(r"[a-z][a-z0-9_]{0,20}", fullmatch=True)
valid_versions = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)


class TestEntryPointValidationPropertyBased:
    """Property-based tests for entry point validation.

    Feature: island-format-migration, Property 4: Entry point validation
    Validates: Requirements 3.1, 3.2, 3.5
    """

    @given(entry_points=valid_ap_island_entry_points())
    @settings(max_examples=100)
    def test_valid_entry_points_pass_validation(self, entry_points: dict[str, dict[str, str]]):
        """
        Property 4: Entry point validation - valid entry points

        *For any* package configuration with at least one valid `ap-island`
        entry point, validation SHALL succeed.

        **Validates: Requirements 3.1, 3.2**
        """
        # Should not raise
        validate_entry_points(entry_points)

    @given(
        name=valid_package_names,
        version=valid_versions,
        entry_points=valid_ap_island_entry_points(),
    )
    @settings(max_examples=100)
    def test_build_succeeds_with_valid_entry_points(
        self,
        name: str,
        version: str,
        entry_points: dict[str, dict[str, str]],
        tmp_path_factory,
    ):
        """
        Property 4: Entry point validation - build success

        *For any* package configuration with at least one valid `ap-island`
        entry point, the build SHALL succeed and the entry points SHALL be
        recorded in `entry_points.txt`.

        **Validates: Requirements 3.1, 3.2**
        """
        tmp_path = tmp_path_factory.mktemp("test")
        src_dir = tmp_path / "src" / name
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text(f"# {name}")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name=name,
            version=version,
            game_name=name.replace("_", " ").title(),
            source_dir=src_dir,
        )

        # Build should succeed
        result = build_island(config, output_dir=output_dir, entry_points=entry_points)

        # Verify entry_points.txt exists and contains the entry points
        with zipfile.ZipFile(result.path, "r") as zf:
            dist_info = get_dist_info_name(name, version)
            ep_content = zf.read(f"{dist_info}/entry_points.txt").decode("utf-8")

            # Check that ap-island section exists
            assert "[ap-island]" in ep_content

            # Check that all entry points are present
            for ep_name, ep_value in entry_points["ap-island"].items():
                assert f"{ep_name} = {ep_value}" in ep_content

    @given(
        name=valid_package_names,
        version=valid_versions,
        entry_points=valid_ap_island_entry_points(),
    )
    @settings(max_examples=100)
    def test_manifest_contains_entry_points(
        self,
        name: str,
        version: str,
        entry_points: dict[str, dict[str, str]],
        tmp_path_factory,
    ):
        """
        Property 4: Entry point validation - manifest inclusion

        *For any* built island package with entry points, the island.json
        manifest SHALL contain the entry_points field.

        **Validates: Requirements 3.1**
        """
        import json

        tmp_path = tmp_path_factory.mktemp("test")
        src_dir = tmp_path / "src" / name
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text(f"# {name}")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name=name,
            version=version,
            game_name=name.replace("_", " ").title(),
            source_dir=src_dir,
        )

        result = build_island(config, output_dir=output_dir, entry_points=entry_points)

        # Verify manifest contains entry_points
        with zipfile.ZipFile(result.path, "r") as zf:
            dist_info = get_dist_info_name(name, version)
            manifest_content = zf.read(f"{dist_info}/island.json").decode("utf-8")
            manifest = json.loads(manifest_content)

            assert "entry_points" in manifest
            assert "ap-island" in manifest["entry_points"]
            assert manifest["entry_points"]["ap-island"] == entry_points["ap-island"]

    @given(invalid_value=invalid_entry_point_values())
    @settings(max_examples=100)
    def test_invalid_entry_point_format_fails_validation(self, invalid_value: str):
        """
        Property 4: Entry point validation - invalid format rejection

        *For any* entry point with invalid format, validation SHALL fail
        with an appropriate error.

        **Validates: Requirements 3.5**
        """
        entry_points = {"ap-island": {"my_game": invalid_value}}
        with pytest.raises((InvalidEntryPointError, MissingEntryPointError)):
            validate_entry_points(entry_points)

    @given(
        name=valid_package_names,
        version=valid_versions,
    )
    @settings(max_examples=100)
    def test_build_without_entry_points_still_works(
        self,
        name: str,
        version: str,
        tmp_path_factory,
    ):
        """
        Test that build_island works without entry points (for backward compatibility).

        Note: The validation is done separately from the build function.
        The build function itself does not require entry points, but
        validate_entry_points() should be called separately to enforce
        the Island format requirement.
        """
        tmp_path = tmp_path_factory.mktemp("test")
        src_dir = tmp_path / "src" / name
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text(f"# {name}")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name=name,
            version=version,
            game_name=name.replace("_", " ").title(),
            source_dir=src_dir,
        )

        # Build without entry points should still work
        # (validation is separate from build)
        result = build_island(config, output_dir=output_dir, entry_points=None)
        assert result.path.exists()

        # But validate_entry_points should fail when called separately
        with pytest.raises(MissingEntryPointError):
            validate_entry_points(None)
