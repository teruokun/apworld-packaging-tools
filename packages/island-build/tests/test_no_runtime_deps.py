# SPDX-License-Identifier: MIT
"""Property-based tests for no external runtime dependencies.

Feature: island-format-migration
Property 6: No external runtime dependencies
Validates: Requirements 4.1

These tests verify that:
- Built island packages do NOT declare external runtime dependencies in METADATA
- The METADATA file is PEP 566 compliant without Requires-Dist entries
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from island_build.config import BuildConfig
from island_build.island import build_island
from island_build.wheel import PackageMetadata


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid package names
valid_package_names = st.from_regex(r"[a-z][a-z0-9_]{0,15}", fullmatch=True)

# Valid versions
valid_versions = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)

# Valid game names
valid_game_names = st.from_regex(r"[A-Z][a-zA-Z0-9 ]{0,20}", fullmatch=True)

# Valid descriptions
valid_descriptions = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=0,
    max_size=100,
)

# Valid author names
valid_authors = st.lists(
    st.from_regex(r"[A-Z][a-zA-Z ]{0,20}", fullmatch=True),
    min_size=0,
    max_size=3,
)

# Valid dependency lists (these should NOT appear in METADATA)
valid_dependencies = st.lists(
    st.from_regex(r"[a-z][a-z0-9_-]{0,15}(>=\d+\.\d+)?", fullmatch=True),
    min_size=0,
    max_size=5,
)


@st.composite
def valid_build_configs(draw, tmp_path_factory):
    """Generate valid BuildConfig instances with source directories."""
    name = draw(valid_package_names)
    version = draw(valid_versions)
    game_name = draw(valid_game_names)
    description = draw(valid_descriptions)
    authors = draw(valid_authors)
    dependencies = draw(valid_dependencies)

    # Create a temporary source directory
    tmp_path = tmp_path_factory.mktemp("src")
    src_dir = tmp_path / name
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text(f"# {name}")
    (src_dir / "world.py").write_text("class World: pass")

    return BuildConfig(
        name=name,
        version=version,
        game_name=game_name,
        source_dir=src_dir,
        description=description,
        authors=authors,
        dependencies=dependencies,
    )


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestNoRuntimeDependenciesProperties:
    """Property-based tests for no external runtime dependencies.

    Feature: island-format-migration, Property 6: No external runtime dependencies
    Validates: Requirements 4.1
    """

    @given(
        name=valid_package_names,
        version=valid_versions,
        description=valid_descriptions,
        authors=valid_authors,
    )
    @settings(max_examples=100)
    def test_package_metadata_no_requires_dist(
        self,
        name: str,
        version: str,
        description: str,
        authors: list[str],
    ):
        """
        Property 6: No external runtime dependencies - METADATA format

        *For any* PackageMetadata instance, the generated METADATA string
        SHALL NOT contain 'Requires-Dist' entries.

        **Validates: Requirements 4.1**
        """
        metadata = PackageMetadata(
            name=name,
            version=version,
            summary=description,
            author=", ".join(authors) if authors else "",
        )

        content = metadata.to_string()

        # METADATA should NOT contain Requires-Dist
        assert "Requires-Dist" not in content

        # But should contain required fields
        assert "Metadata-Version:" in content
        assert f"Name: {name}" in content
        assert f"Version: {version}" in content

    @given(
        name=valid_package_names,
        version=valid_versions,
        game_name=valid_game_names,
        dependencies=valid_dependencies,
    )
    @settings(max_examples=100)
    def test_built_island_metadata_no_requires_dist(
        self,
        name: str,
        version: str,
        game_name: str,
        dependencies: list[str],
        tmp_path_factory,
    ):
        """
        Property 6: No external runtime dependencies - built package

        *For any* built island package (even with dependencies configured),
        the METADATA file SHALL NOT contain 'Requires-Dist' entries.

        **Validates: Requirements 4.1**
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
            game_name=game_name,
            source_dir=src_dir,
            dependencies=dependencies,  # These should NOT appear in METADATA
        )

        entry_points = {"ap-island": {name: f"{name}.world:World"}}
        result = build_island(config, output_dir=output_dir, entry_points=entry_points)

        # Extract and check METADATA
        with zipfile.ZipFile(result.path, "r") as zf:
            # Find METADATA file
            metadata_files = [n for n in zf.namelist() if n.endswith("/METADATA")]
            assert len(metadata_files) == 1

            metadata_content = zf.read(metadata_files[0]).decode("utf-8")

            # METADATA should NOT contain Requires-Dist
            assert "Requires-Dist" not in metadata_content

            # But should contain required PEP 566 fields
            assert "Metadata-Version: 2.1" in metadata_content
            assert f"Name: {name}" in metadata_content
            assert f"Version: {version}" in metadata_content

    @given(
        name=valid_package_names,
        version=valid_versions,
    )
    @settings(max_examples=100)
    def test_metadata_pep566_compliance(
        self,
        name: str,
        version: str,
    ):
        """
        Property 6: No external runtime dependencies - PEP 566 compliance

        *For any* PackageMetadata, the output SHALL be PEP 566 compliant
        with required fields present and no runtime dependencies.

        **Validates: Requirements 4.1**
        """
        metadata = PackageMetadata(
            name=name,
            version=version,
        )

        content = metadata.to_string()
        lines = content.strip().split("\n")

        # Check required fields are present
        field_names = [line.split(":")[0] for line in lines if ":" in line]

        assert "Metadata-Version" in field_names
        assert "Name" in field_names
        assert "Version" in field_names

        # Ensure no dependency fields
        assert "Requires-Dist" not in field_names
        assert "Requires-Python" not in field_names or True  # Python version is OK
        assert "Requires-External" not in field_names

    @given(
        name=valid_package_names,
        version=valid_versions,
        game_name=valid_game_names,
    )
    @settings(max_examples=100)
    def test_island_self_contained(
        self,
        name: str,
        version: str,
        game_name: str,
        tmp_path_factory,
    ):
        """
        Property 6: No external runtime dependencies - self-containment

        *For any* built island package, the package SHALL be self-contained
        with no external runtime dependency declarations.

        **Validates: Requirements 4.1**
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
            game_name=game_name,
            source_dir=src_dir,
        )

        entry_points = {"ap-island": {name: f"{name}.world:World"}}
        result = build_island(config, output_dir=output_dir, entry_points=entry_points)

        # Verify the package is self-contained
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()

            # Should have source files (use normalized name since that's what's in the archive)
            normalized_name = config.normalized_name
            assert any(normalized_name in n for n in names)

            # Should have dist-info
            dist_info_files = [n for n in names if ".dist-info/" in n]
            assert len(dist_info_files) > 0

            # Check METADATA for no external deps
            metadata_files = [n for n in names if n.endswith("/METADATA")]
            assert len(metadata_files) == 1

            metadata_content = zf.read(metadata_files[0]).decode("utf-8")
            assert "Requires-Dist" not in metadata_content

    @given(
        name=valid_package_names,
        version=valid_versions,
        keywords=st.lists(st.from_regex(r"[a-z]{3,10}", fullmatch=True), max_size=5),
        license_str=st.sampled_from(["MIT", "Apache-2.0", "GPL-3.0", ""]),
    )
    @settings(max_examples=100)
    def test_metadata_optional_fields_no_deps(
        self,
        name: str,
        version: str,
        keywords: list[str],
        license_str: str,
    ):
        """
        Property 6: No external runtime dependencies - optional fields

        *For any* PackageMetadata with optional fields, the output SHALL
        include those fields but still NOT include Requires-Dist.

        **Validates: Requirements 4.1**
        """
        metadata = PackageMetadata(
            name=name,
            version=version,
            keywords=keywords,
            license=license_str,
        )

        content = metadata.to_string()

        # Should NOT have Requires-Dist
        assert "Requires-Dist" not in content

        # Should have optional fields if provided
        if keywords:
            assert "Keywords:" in content
        if license_str:
            assert f"License: {license_str}" in content
