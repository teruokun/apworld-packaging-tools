# SPDX-License-Identifier: MIT
"""Tests for Island binary distribution builder module.

Feature: island-format-migration
Property 4: Entry point validation
Validates: Requirements 3.1, 3.2, 3.5
"""

import json
import zipfile

import pytest
from hypothesis import given, settings, strategies as st

from island_build.config import BuildConfig
from island_build.filename import UNIVERSAL_TAG, PlatformTag
from island_build.island import (
    ENTRY_POINT_PATTERN,
    InvalidEntryPointError,
    IslandError,
    MissingEntryPointError,
    build_island,
    validate_entry_point_format,
    validate_entry_points,
)


# Default entry points for tests
DEFAULT_ENTRY_POINTS = {"ap-island": {"my_game": "my_game.world:MyWorld"}}


class TestBuildIsland:
    """Tests for build_island function."""

    def test_creates_island_file(self, tmp_path):
        # Create source directory
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("# My Game Island")
        (src_dir / "world.py").write_text("class MyWorld: pass")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
        )

        result = build_island(config, output_dir=output_dir, entry_points=DEFAULT_ENTRY_POINTS)

        assert result.path.exists()
        assert result.filename == "my_game-1.0.0-py3-none-any.island"
        assert result.size > 0
        assert result.is_pure_python is True
        assert result.platform_tag == UNIVERSAL_TAG

    def test_island_contains_manifest(self, tmp_path):
        # Create source directory
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
            description="Test game",
            authors=["Test Author"],
        )

        result = build_island(config, output_dir=output_dir, entry_points=DEFAULT_ENTRY_POINTS)

        # Verify manifest in archive (now in dist-info directory)
        with zipfile.ZipFile(result.path, "r") as zf:
            manifest_path = "my_game-1.0.0.dist-info/island.json"
            assert manifest_path in zf.namelist()

            manifest_content = zf.read(manifest_path).decode("utf-8")
            manifest = json.loads(manifest_content)

            assert manifest["game"] == "My Game"
            assert manifest["world_version"] == "1.0.0"
            assert manifest["description"] == "Test game"
            assert manifest["authors"] == ["Test Author"]
            assert manifest["pure_python"] is True

    def test_island_structure(self, tmp_path):
        # Create source directory with nested structure
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")
        (src_dir / "world.py").write_text("class MyWorld: pass")

        subdir = src_dir / "data"
        subdir.mkdir()
        (subdir / "__init__.py").write_text("")
        (subdir / "items.py").write_text("ITEMS = []")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
        )

        result = build_island(config, output_dir=output_dir, entry_points=DEFAULT_ENTRY_POINTS)

        # Verify structure
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()
            # Source files
            assert "my_game/__init__.py" in names
            assert "my_game/world.py" in names
            assert "my_game/data/__init__.py" in names
            assert "my_game/data/items.py" in names
            # Wheel metadata files in dist-info
            assert "my_game-1.0.0.dist-info/WHEEL" in names
            assert "my_game-1.0.0.dist-info/METADATA" in names
            assert "my_game-1.0.0.dist-info/RECORD" in names
            assert "my_game-1.0.0.dist-info/island.json" in names
            # Entry points file
            assert "my_game-1.0.0.dist-info/entry_points.txt" in names

    def test_island_with_vendor_dir(self, tmp_path):
        # Create source directory
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")

        # Create vendor directory
        vendor_dir = tmp_path / "vendor"
        vendor_dir.mkdir()
        (vendor_dir / "__init__.py").write_text("")
        (vendor_dir / "yaml").mkdir()
        (vendor_dir / "yaml" / "__init__.py").write_text("# vendored yaml")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
        )

        result = build_island(
            config, output_dir=output_dir, vendor_dir=vendor_dir, entry_points=DEFAULT_ENTRY_POINTS
        )

        # Verify vendor files included
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()
            assert any("_vendor" in n for n in names)
            assert "my_game/_vendor/yaml/__init__.py" in names

    def test_nonexistent_source_raises(self, tmp_path):
        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=tmp_path / "nonexistent",
        )

        with pytest.raises(IslandError, match="does not exist"):
            build_island(config, output_dir=tmp_path / "dist", entry_points=DEFAULT_ENTRY_POINTS)

    def test_custom_platform_tag(self, tmp_path):
        # Create source directory
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
        )

        custom_tag = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
        result = build_island(
            config,
            output_dir=output_dir,
            platform_tag=custom_tag,
            entry_points=DEFAULT_ENTRY_POINTS,
        )

        assert result.filename == "my_game-1.0.0-cp311-cp311-win_amd64.island"
        assert result.platform_tag == custom_tag

    def test_manifest_includes_ap_versions(self, tmp_path):
        # Create source directory
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
            minimum_ap_version="0.5.0",
            maximum_ap_version="0.6.99",
        )

        result = build_island(config, output_dir=output_dir, entry_points=DEFAULT_ENTRY_POINTS)

        assert result.manifest["minimum_ap_version"] == "0.5.0"
        assert result.manifest["maximum_ap_version"] == "0.6.99"


class TestEntryPointValidation:
    """Tests for entry point validation functions."""

    def test_validate_entry_points_missing_raises(self):
        """Test that missing entry points raises MissingEntryPointError."""
        with pytest.raises(MissingEntryPointError):
            validate_entry_points(None)

    def test_validate_entry_points_empty_raises(self):
        """Test that empty entry points raises MissingEntryPointError."""
        with pytest.raises(MissingEntryPointError):
            validate_entry_points({})

    def test_validate_entry_points_no_ap_island_raises(self):
        """Test that entry points without ap-island raises MissingEntryPointError."""
        with pytest.raises(MissingEntryPointError):
            validate_entry_points({"console_scripts": {"cli": "my_game.cli:main"}})

    def test_validate_entry_points_empty_ap_island_raises(self):
        """Test that empty ap-island group raises MissingEntryPointError."""
        with pytest.raises(MissingEntryPointError):
            validate_entry_points({"ap-island": {}})

    def test_validate_entry_points_valid_passes(self):
        """Test that valid entry points pass validation."""
        entry_points = {"ap-island": {"my_game": "my_game.world:MyWorld"}}
        validate_entry_points(entry_points)  # Should not raise

    def test_validate_entry_points_multiple_valid_passes(self):
        """Test that multiple valid entry points pass validation."""
        entry_points = {
            "ap-island": {
                "my_game": "my_game.world:MyWorld",
                "my_game_alt": "my_game.alt:AltWorld",
            }
        }
        validate_entry_points(entry_points)  # Should not raise

    def test_validate_entry_point_format_valid(self):
        """Test valid entry point formats."""
        validate_entry_point_format("my_game", "my_game.world:MyWorld")
        validate_entry_point_format("test", "module:Class")
        validate_entry_point_format("nested", "a.b.c.d:ClassName")

    def test_validate_entry_point_format_empty_raises(self):
        """Test that empty value raises InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError):
            validate_entry_point_format("test", "")

    def test_validate_entry_point_format_no_colon_raises(self):
        """Test that missing colon raises InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError):
            validate_entry_point_format("test", "my_game.world.MyWorld")

    def test_validate_entry_point_format_invalid_module_raises(self):
        """Test that invalid module path raises InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError):
            validate_entry_point_format("test", "123invalid:Class")

    def test_validate_entry_point_format_invalid_attr_raises(self):
        """Test that invalid attribute raises InvalidEntryPointError."""
        with pytest.raises(InvalidEntryPointError):
            validate_entry_point_format("test", "module:123invalid")

    def test_build_island_without_entry_points_succeeds(self, tmp_path):
        """Test that building without entry points succeeds (validation is separate)."""
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
        )

        # Build should succeed without entry points
        result = build_island(config, output_dir=tmp_path / "dist")
        assert result.path.exists()

        # But validation should fail
        with pytest.raises(MissingEntryPointError):
            validate_entry_points(None)

    def test_build_island_with_invalid_entry_point_succeeds(self, tmp_path):
        """Test that building with invalid entry point succeeds (validation is separate)."""
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
        )

        invalid_entry_points = {"ap-island": {"my_game": "invalid_format"}}

        # Build should succeed (validation is separate)
        result = build_island(
            config, output_dir=tmp_path / "dist", entry_points=invalid_entry_points
        )
        assert result.path.exists()

        # But validation should fail
        with pytest.raises(InvalidEntryPointError):
            validate_entry_points(invalid_entry_points)


# =============================================================================
# Property-Based Tests using Hypothesis
# =============================================================================

# Strategies for generating valid components
valid_package_names = st.from_regex(r"[a-z][a-z0-9_]{0,20}", fullmatch=True)
valid_versions = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)
valid_module_names = st.from_regex(r"[a-z_][a-z0-9_]{0,15}", fullmatch=True)
valid_class_names = st.from_regex(r"[A-Z][a-zA-Z0-9]{0,15}", fullmatch=True)


@st.composite
def valid_entry_point_values(draw):
    """Generate valid entry point values in format module.path:ClassName."""
    module_parts = draw(st.lists(valid_module_names, min_size=1, max_size=3))
    module_path = ".".join(module_parts)
    class_name = draw(valid_class_names)
    return f"{module_path}:{class_name}"


@st.composite
def valid_ap_island_entry_points(draw):
    """Generate valid ap-island entry points dict."""
    num_entries = draw(st.integers(min_value=1, max_value=3))
    entries = {}
    for _ in range(num_entries):
        name = draw(valid_module_names)
        value = draw(valid_entry_point_values())
        entries[name] = value
    return {"ap-island": entries}


@st.composite
def invalid_entry_point_values(draw):
    """Generate invalid entry point values."""
    invalid_type = draw(st.sampled_from(["no_colon", "invalid_module", "invalid_attr", "empty"]))
    if invalid_type == "no_colon":
        return draw(st.from_regex(r"[a-z_][a-z0-9_.]{0,20}", fullmatch=True))
    elif invalid_type == "invalid_module":
        return f"123invalid:{draw(valid_class_names)}"
    elif invalid_type == "invalid_attr":
        return f"{draw(valid_module_names)}:123invalid"
    else:
        return ""


class TestEntryPointValidationPropertyBased:
    """Property-based tests for entry point validation.

    Feature: island-format-migration, Property 4: Entry point validation
    Validates: Requirements 3.1, 3.2, 3.5
    """

    @given(entry_points=valid_ap_island_entry_points())
    @settings(max_examples=100)
    def test_valid_entry_points_pass_validation(self, entry_points: dict):
        """
        Property 4: Entry point validation - valid entry points

        *For any* valid ap-island entry point configuration,
        validation SHALL succeed without raising exceptions.

        **Validates: Requirements 3.1, 3.2**
        """
        # Should not raise any exception
        validate_entry_points(entry_points)

    @given(
        name=valid_package_names,
        version=valid_versions,
        entry_points=valid_ap_island_entry_points(),
    )
    @settings(max_examples=100)
    def test_build_succeeds_with_valid_entry_points(
        self, name: str, version: str, entry_points: dict, tmp_path_factory
    ):
        """
        Property 4: Entry point validation - build success

        *For any* valid package configuration with valid ap-island entry points,
        the build SHALL succeed and produce a valid island file.

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

        result = build_island(config, output_dir=output_dir, entry_points=entry_points)

        # Verify build succeeded
        assert result.path.exists()
        assert result.size > 0

        # Verify entry_points.txt is in the archive
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()
            # Find the entry_points.txt file (dist-info name may vary due to normalization)
            entry_points_files = [n for n in names if n.endswith("/entry_points.txt")]
            assert (
                len(entry_points_files) == 1
            ), f"Expected 1 entry_points.txt, found {entry_points_files}"

    @given(
        name=valid_package_names,
        version=valid_versions,
    )
    @settings(max_examples=100)
    def test_validation_fails_without_entry_points(self, name: str, version: str):
        """
        Property 4: Entry point validation - missing entry points

        *For any* package configuration, validation without entry points
        SHALL fail with MissingEntryPointError.

        **Validates: Requirements 3.2, 3.5**
        """
        # Validation should fail for None
        with pytest.raises(MissingEntryPointError):
            validate_entry_points(None)

        # Validation should fail for empty dict
        with pytest.raises(MissingEntryPointError):
            validate_entry_points({})

    @given(
        name=valid_package_names,
        version=valid_versions,
    )
    @settings(max_examples=100)
    def test_validation_fails_with_empty_ap_island(self, name: str, version: str):
        """
        Property 4: Entry point validation - empty ap-island

        *For any* package configuration, validation with empty ap-island
        entry points SHALL fail with MissingEntryPointError.

        **Validates: Requirements 3.2, 3.5**
        """
        with pytest.raises(MissingEntryPointError):
            validate_entry_points({"ap-island": {}})

    @given(entry_point_value=valid_entry_point_values())
    @settings(max_examples=100)
    def test_valid_entry_point_format_matches_pattern(self, entry_point_value: str):
        """
        Property 4: Entry point validation - format compliance

        *For any* generated valid entry point value,
        it SHALL match the ENTRY_POINT_PATTERN regex.

        **Validates: Requirements 3.1**
        """
        assert ENTRY_POINT_PATTERN.match(entry_point_value) is not None
        # Should not raise
        validate_entry_point_format("test", entry_point_value)

    @given(invalid_value=invalid_entry_point_values())
    @settings(max_examples=100)
    def test_invalid_entry_point_format_raises(self, invalid_value: str):
        """
        Property 4: Entry point validation - invalid format rejection

        *For any* invalid entry point value,
        validation SHALL raise InvalidEntryPointError.

        **Validates: Requirements 3.5**
        """
        with pytest.raises(InvalidEntryPointError):
            validate_entry_point_format("test", invalid_value)
