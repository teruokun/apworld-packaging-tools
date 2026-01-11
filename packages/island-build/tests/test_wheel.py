# SPDX-License-Identifier: MIT
"""Tests for wheel metadata generation module.

Feature: island-format-migration
Property 2: Wheel structure compliance
Property 3: RECORD file integrity
Validates: Requirements 2.1, 2.3, 2.4, 2.5
"""

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from island_build.config import BuildConfig
from island_build.filename import PlatformTag
from island_build.island import build_island
from island_build.wheel import (
    GENERATOR,
    WHEEL_VERSION,
    EntryPointsFile,
    PackageMetadata,
    RecordEntry,
    RecordFile,
    WheelMetadata,
    compute_content_hash,
    compute_file_hash,
    get_dist_info_name,
)


# =============================================================================
# Unit Tests for WheelMetadata
# =============================================================================


class TestWheelMetadata:
    """Unit tests for WheelMetadata class."""

    def test_default_values(self):
        """Test default values are set correctly."""
        meta = WheelMetadata()
        assert meta.wheel_version == WHEEL_VERSION
        assert meta.generator == GENERATOR
        assert meta.root_is_purelib is True
        assert meta.tags == []

    def test_to_string_basic(self):
        """Test basic WHEEL file generation."""
        meta = WheelMetadata(tags=["py3-none-any"])
        content = meta.to_string()

        assert "Wheel-Version: 1.0" in content
        assert f"Generator: {GENERATOR}" in content
        assert "Root-Is-Purelib: true" in content
        assert "Tag: py3-none-any" in content

    def test_to_string_not_purelib(self):
        """Test WHEEL file with Root-Is-Purelib: false."""
        meta = WheelMetadata(root_is_purelib=False, tags=["cp311-cp311-win_amd64"])
        content = meta.to_string()

        assert "Root-Is-Purelib: false" in content

    def test_to_string_multiple_tags(self):
        """Test WHEEL file with multiple tags."""
        meta = WheelMetadata(tags=["py3-none-any", "py310-none-any"])
        content = meta.to_string()

        assert "Tag: py3-none-any" in content
        assert "Tag: py310-none-any" in content

    def test_from_platform_tag_pure_python(self):
        """Test creating WheelMetadata from pure Python platform tag."""
        tag = PlatformTag.pure_python()
        meta = WheelMetadata.from_platform_tag(tag)

        assert meta.root_is_purelib is True
        assert "py3-none-any" in meta.tags

    def test_from_platform_tag_platform_specific(self):
        """Test creating WheelMetadata from platform-specific tag."""
        tag = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")
        meta = WheelMetadata.from_platform_tag(tag)

        assert meta.root_is_purelib is False
        assert "cp311-cp311-win_amd64" in meta.tags


# =============================================================================
# Unit Tests for PackageMetadata
# =============================================================================


class TestPackageMetadata:
    """Unit tests for PackageMetadata class."""

    def test_minimal_metadata(self):
        """Test minimal METADATA generation."""
        meta = PackageMetadata(name="my-game", version="1.0.0")
        content = meta.to_string()

        assert "Metadata-Version: 2.1" in content
        assert "Name: my-game" in content
        assert "Version: 1.0.0" in content

    def test_full_metadata(self):
        """Test full METADATA generation with all fields."""
        meta = PackageMetadata(
            name="my-game",
            version="1.0.0",
            summary="A test game",
            author="Test Author",
            license="MIT",
            keywords=["game", "test"],
            home_page="https://example.com",
            project_urls={"Repository": "https://github.com/test/test"},
            description="Long description here",
        )
        content = meta.to_string()

        assert "Summary: A test game" in content
        assert "Author: Test Author" in content
        assert "License: MIT" in content
        assert "Keywords: game,test" in content
        assert "Home-page: https://example.com" in content
        assert "Project-URL: Repository, https://github.com/test/test" in content
        assert "Long description here" in content

    def test_no_requires_dist(self):
        """Test that METADATA does not contain Requires-Dist."""
        meta = PackageMetadata(name="my-game", version="1.0.0")
        content = meta.to_string()

        assert "Requires-Dist" not in content

    def test_from_build_config(self, tmp_path):
        """Test creating PackageMetadata from BuildConfig."""
        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=tmp_path,
            description="Test description",
            authors=["Author One", "Author Two"],
            license="MIT",
            homepage="https://example.com",
            repository="https://github.com/test/test",
            keywords=["game", "test"],
        )
        meta = PackageMetadata.from_build_config(config)

        assert meta.name == "my-game"
        assert meta.version == "1.0.0"
        assert meta.summary == "Test description"
        assert meta.author == "Author One, Author Two"
        assert meta.license == "MIT"


# =============================================================================
# Unit Tests for RecordFile
# =============================================================================


class TestRecordFile:
    """Unit tests for RecordFile class."""

    def test_empty_record(self):
        """Test empty RECORD file."""
        record = RecordFile(record_path="test-1.0.0.dist-info/RECORD")
        content = record.to_string()

        assert "test-1.0.0.dist-info/RECORD,," in content

    def test_add_content(self):
        """Test adding content to RECORD."""
        record = RecordFile(record_path="test-1.0.0.dist-info/RECORD")
        record.add_content("test/__init__.py", b"# init")
        content = record.to_string()

        assert "test/__init__.py,sha256=" in content
        assert "test-1.0.0.dist-info/RECORD,," in content

    def test_add_file(self, tmp_path):
        """Test adding file to RECORD."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# test file")

        record = RecordFile(record_path="test-1.0.0.dist-info/RECORD")
        record.add_file("test/test.py", test_file)
        content = record.to_string()

        assert "test/test.py,sha256=" in content


class TestRecordEntry:
    """Unit tests for RecordEntry class."""

    def test_entry_with_hash(self):
        """Test entry with hash and size."""
        entry = RecordEntry(path="test/__init__.py", hash_digest="sha256=abc123", size=42)
        assert entry.to_string() == "test/__init__.py,sha256=abc123,42"

    def test_entry_without_hash(self):
        """Test entry without hash (for RECORD itself)."""
        entry = RecordEntry(path="test-1.0.0.dist-info/RECORD")
        assert entry.to_string() == "test-1.0.0.dist-info/RECORD,,"


# =============================================================================
# Unit Tests for EntryPointsFile
# =============================================================================


class TestEntryPointsFile:
    """Unit tests for EntryPointsFile class."""

    def test_empty_entry_points(self):
        """Test empty entry points file."""
        ep = EntryPointsFile()
        assert ep.to_string() == ""

    def test_single_entry_point(self):
        """Test single entry point."""
        ep = EntryPointsFile()
        ep.add_entry_point("ap-island", "my_game", "my_game.world:MyGameWorld")
        content = ep.to_string()

        assert "[ap-island]" in content
        assert "my_game = my_game.world:MyGameWorld" in content

    def test_multiple_groups(self):
        """Test multiple entry point groups."""
        ep = EntryPointsFile()
        ep.add_entry_point("ap-island", "my_game", "my_game.world:MyGameWorld")
        ep.add_entry_point("console_scripts", "my-cli", "my_game.cli:main")
        content = ep.to_string()

        assert "[ap-island]" in content
        assert "[console_scripts]" in content

    def test_from_pyproject_dict(self):
        """Test creating from pyproject.toml dict."""
        pyproject = {
            "project": {"entry-points": {"ap-island": {"my_game": "my_game.world:MyGameWorld"}}}
        }
        ep = EntryPointsFile.from_pyproject_dict(pyproject)

        assert ep.has_ap_island_entry_points()
        assert ep.groups["ap-island"]["my_game"] == "my_game.world:MyGameWorld"

    def test_has_ap_island_entry_points_true(self):
        """Test has_ap_island_entry_points returns True when present."""
        ep = EntryPointsFile()
        ep.add_entry_point("ap-island", "my_game", "my_game.world:MyGameWorld")
        assert ep.has_ap_island_entry_points() is True

    def test_has_ap_island_entry_points_false(self):
        """Test has_ap_island_entry_points returns False when absent."""
        ep = EntryPointsFile()
        assert ep.has_ap_island_entry_points() is False


# =============================================================================
# Unit Tests for Helper Functions
# =============================================================================


class TestHelperFunctions:
    """Unit tests for helper functions."""

    def test_get_dist_info_name(self):
        """Test dist-info directory name generation."""
        assert get_dist_info_name("my-game", "1.0.0") == "my_game-1.0.0.dist-info"
        assert get_dist_info_name("Pokemon-Emerald", "2.1.0") == "pokemon_emerald-2.1.0.dist-info"

    def test_compute_content_hash(self):
        """Test content hash computation."""
        content = b"hello world"
        hash_str, size = compute_content_hash(content)

        assert hash_str.startswith("sha256=")
        assert size == 11

        # Verify the hash is correct
        expected_hash = hashlib.sha256(content).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_hash).rstrip(b"=").decode("ascii")
        assert hash_str == f"sha256={expected_b64}"

    def test_compute_file_hash(self, tmp_path):
        """Test file hash computation."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        hash_str, size = compute_file_hash(test_file)

        assert hash_str.startswith("sha256=")
        assert size == 11


# =============================================================================
# Property-Based Tests using Hypothesis
# =============================================================================

# Strategies for generating valid components
valid_package_names = st.from_regex(r"[a-z][a-z0-9_]{0,20}", fullmatch=True)
valid_versions = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)
valid_descriptions = st.text(
    min_size=0, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"))
)
valid_authors = st.lists(
    st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N"))),
    min_size=0,
    max_size=3,
)

# Valid python tags
valid_python_tags = st.sampled_from(["py3", "cp311", "cp312", "cp313"])
valid_abi_tags = st.sampled_from(["none", "cp311", "cp312", "abi3"])
valid_platform_tags = st.sampled_from(
    [
        "any",
        "win_amd64",
        "win_arm64",
        "macosx_11_0_x86_64",
        "macosx_11_0_arm64",
        "manylinux_2_17_x86_64",
        "manylinux_2_17_aarch64",
    ]
)


@st.composite
def valid_platform_tag_objects(draw):
    """Generate valid PlatformTag objects."""
    return PlatformTag(
        python=draw(valid_python_tags),
        abi=draw(valid_abi_tags),
        platform=draw(valid_platform_tags),
    )


@st.composite
def valid_build_configs(draw, tmp_path_factory):
    """Generate valid BuildConfig objects with source directories."""
    name = draw(valid_package_names)
    version = draw(valid_versions)
    description = draw(valid_descriptions)
    authors = draw(valid_authors)

    # Create a temporary source directory
    src_dir = tmp_path_factory.mktemp("src") / name
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text(f"# {name} package")
    (src_dir / "world.py").write_text(f"class {name.title()}World: pass")

    return BuildConfig(
        name=name,
        version=version,
        game_name=name.replace("_", " ").title(),
        source_dir=src_dir,
        description=description,
        authors=authors,
    )


class TestWheelStructurePropertyBased:
    """Property-based tests for wheel structure compliance.

    Feature: island-format-migration, Property 2: Wheel structure compliance
    Validates: Requirements 2.1, 2.3, 2.4, 2.5
    """

    @given(
        name=valid_package_names,
        version=valid_versions,
        platform_tag=valid_platform_tag_objects(),
    )
    @settings(max_examples=100)
    def test_wheel_structure_contains_required_files(
        self, name: str, version: str, platform_tag: PlatformTag, tmp_path_factory
    ):
        """
        Property 2: Wheel structure compliance

        *For any* built island package, extracting the archive SHALL reveal
        a valid wheel structure containing: a `{name}-{version}.dist-info/`
        directory with `WHEEL`, `METADATA`, and `RECORD` files.

        **Validates: Requirements 2.1, 2.3, 2.4, 2.5**
        """
        # Create source directory
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

        result = build_island(config, output_dir=output_dir, platform_tag=platform_tag)

        # Verify wheel structure
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()
            dist_info = get_dist_info_name(name, version)

            # Check required dist-info files exist
            assert f"{dist_info}/WHEEL" in names, f"WHEEL file missing in {names}"
            assert f"{dist_info}/METADATA" in names, f"METADATA file missing in {names}"
            assert f"{dist_info}/RECORD" in names, f"RECORD file missing in {names}"

    @given(
        name=valid_package_names,
        version=valid_versions,
    )
    @settings(max_examples=100)
    def test_wheel_file_format_compliance(self, name: str, version: str, tmp_path_factory):
        """
        Property 2: Wheel structure compliance - WHEEL file format

        *For any* built island package, the WHEEL file SHALL contain
        Wheel-Version, Generator, Root-Is-Purelib, and Tag fields.

        **Validates: Requirements 2.1, 2.3**
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

        result = build_island(config, output_dir=output_dir)

        with zipfile.ZipFile(result.path, "r") as zf:
            dist_info = get_dist_info_name(name, version)
            wheel_content = zf.read(f"{dist_info}/WHEEL").decode("utf-8")

            assert "Wheel-Version:" in wheel_content
            assert "Generator:" in wheel_content
            assert "Root-Is-Purelib:" in wheel_content
            assert "Tag:" in wheel_content

    @given(
        name=valid_package_names,
        version=valid_versions,
        description=valid_descriptions,
    )
    @settings(max_examples=100)
    def test_metadata_file_format_compliance(
        self, name: str, version: str, description: str, tmp_path_factory
    ):
        """
        Property 2: Wheel structure compliance - METADATA file format

        *For any* built island package, the METADATA file SHALL contain
        Metadata-Version, Name, and Version fields, and SHALL NOT contain
        Requires-Dist entries.

        **Validates: Requirements 2.4, 4.1**
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
            description=description,
        )

        result = build_island(config, output_dir=output_dir)

        with zipfile.ZipFile(result.path, "r") as zf:
            dist_info = get_dist_info_name(name, version)
            metadata_content = zf.read(f"{dist_info}/METADATA").decode("utf-8")

            assert "Metadata-Version:" in metadata_content
            assert f"Name: {name}" in metadata_content
            assert f"Version: {version}" in metadata_content
            # Island packages should NOT have Requires-Dist
            assert "Requires-Dist" not in metadata_content


class TestRecordIntegrityPropertyBased:
    """Property-based tests for RECORD file integrity.

    Feature: island-format-migration, Property 3: RECORD file integrity
    Validates: Requirements 2.5
    """

    @given(
        name=valid_package_names,
        version=valid_versions,
    )
    @settings(max_examples=100)
    def test_record_lists_all_files(self, name: str, version: str, tmp_path_factory):
        """
        Property 3: RECORD file integrity - file listing

        *For any* built island package, every file in the archive (except RECORD)
        SHALL be listed in the RECORD file.

        **Validates: Requirements 2.5**
        """
        tmp_path = tmp_path_factory.mktemp("test")
        src_dir = tmp_path / "src" / name
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text(f"# {name}")
        (src_dir / "world.py").write_text("class World: pass")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name=name,
            version=version,
            game_name=name.replace("_", " ").title(),
            source_dir=src_dir,
        )

        result = build_island(config, output_dir=output_dir)

        with zipfile.ZipFile(result.path, "r") as zf:
            dist_info = get_dist_info_name(name, version)
            record_content = zf.read(f"{dist_info}/RECORD").decode("utf-8")

            # Parse RECORD entries
            record_files = set()
            for line in record_content.strip().split("\n"):
                if line:
                    path = line.split(",")[0]
                    record_files.add(path)

            # Check all files in archive are in RECORD
            archive_files = set(zf.namelist())
            for archive_file in archive_files:
                assert archive_file in record_files, f"{archive_file} not in RECORD"

    @given(
        name=valid_package_names,
        version=valid_versions,
    )
    @settings(max_examples=100)
    def test_record_checksums_match(self, name: str, version: str, tmp_path_factory):
        """
        Property 3: RECORD file integrity - checksum verification

        *For any* built island package, the SHA256 checksum of each file
        SHALL match the recorded value in RECORD.

        **Validates: Requirements 2.5**
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

        result = build_island(config, output_dir=output_dir)

        with zipfile.ZipFile(result.path, "r") as zf:
            dist_info = get_dist_info_name(name, version)
            record_content = zf.read(f"{dist_info}/RECORD").decode("utf-8")

            # Parse RECORD and verify checksums
            for line in record_content.strip().split("\n"):
                if not line:
                    continue

                parts = line.split(",")
                path = parts[0]
                recorded_hash = parts[1] if len(parts) > 1 else ""

                # RECORD itself has no hash
                if path.endswith("/RECORD"):
                    assert recorded_hash == "", f"RECORD should have empty hash"
                    continue

                # Verify hash matches
                if recorded_hash:
                    file_content = zf.read(path)
                    computed_hash, _ = compute_content_hash(file_content)
                    assert computed_hash == recorded_hash, (
                        f"Hash mismatch for {path}: "
                        f"computed={computed_hash}, recorded={recorded_hash}"
                    )

    @given(
        name=valid_package_names,
        version=valid_versions,
    )
    @settings(max_examples=100)
    def test_record_sizes_match(self, name: str, version: str, tmp_path_factory):
        """
        Property 3: RECORD file integrity - size verification

        *For any* built island package, the size of each file
        SHALL match the recorded value in RECORD.

        **Validates: Requirements 2.5**
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

        result = build_island(config, output_dir=output_dir)

        with zipfile.ZipFile(result.path, "r") as zf:
            dist_info = get_dist_info_name(name, version)
            record_content = zf.read(f"{dist_info}/RECORD").decode("utf-8")

            # Parse RECORD and verify sizes
            for line in record_content.strip().split("\n"):
                if not line:
                    continue

                parts = line.split(",")
                path = parts[0]
                recorded_size = parts[2] if len(parts) > 2 else ""

                # RECORD itself has no size
                if path.endswith("/RECORD"):
                    assert recorded_size == "", f"RECORD should have empty size"
                    continue

                # Verify size matches
                if recorded_size:
                    file_content = zf.read(path)
                    actual_size = len(file_content)
                    assert actual_size == int(recorded_size), (
                        f"Size mismatch for {path}: "
                        f"actual={actual_size}, recorded={recorded_size}"
                    )
