# SPDX-License-Identifier: MIT
"""Integration test: Legacy migration flow.

Tests the complete flow of:
1. Migrating a legacy archipelago.json manifest
2. Building from the migrated project
3. Verifying compatibility with the modern schema

NOTE: These tests are for Task 9 (Migration Tooling) which is not yet implemented.
They are marked as skipped until the migration functionality is complete.
"""

import json
import os
import shutil
import zipfile
from pathlib import Path

import pytest

from island_build.island import build_island
from island_build.config import BuildConfig
from island_manifest import (
    CURRENT_SCHEMA_VERSION,
    MIN_COMPATIBLE_VERSION,
    validate_manifest,
)


@pytest.mark.skip(
    reason="Migration tooling (Task 9) not yet implemented - island format uses island.json in dist-info"
)
class TestLegacyMigrationFlow:
    """Integration tests for the legacy migration flow."""

    @pytest.fixture
    def sample_source_dir(self) -> Path:
        """Get the sample source directory."""
        return Path(__file__).parent / "sample_island" / "src" / "sample_game"

    @pytest.fixture
    def legacy_manifest_minimal(self) -> dict:
        """Create a minimal legacy manifest (only required fields)."""
        return {
            "game": "Legacy Game",
            "version": 6,  # Older schema version
            "compatible_version": 5,
        }

    @pytest.fixture
    def legacy_manifest_full(self) -> dict:
        """Create a full legacy manifest with all common fields."""
        return {
            "game": "Full Legacy Game",
            "version": 6,
            "compatible_version": 5,
            "data_version": 1,  # Legacy field that maps to world_version
            "minimum_ap_version": "0.4.0",
            "maximum_ap_version": "0.5.99",
        }

    @pytest.fixture
    def legacy_manifest_with_extras(self) -> dict:
        """Create a legacy manifest with extra metadata."""
        return {
            "game": "Extra Legacy Game",
            "version": 7,
            "compatible_version": 6,
            "world_version": "1.2.3",
            "authors": ["Legacy Author"],
            "description": "A legacy game description",
            "license": "MIT",
            "homepage": "https://example.com",
            "repository": "https://github.com/example/repo",
            "keywords": ["legacy", "test"],
        }

    def _migrate_manifest(self, legacy: dict) -> dict:
        """Migrate a legacy manifest to modern schema.

        This simulates what the CLI migrate command does.
        """
        migrated = {}

        # Required fields
        migrated["game"] = legacy.get("game", "Unknown Game")
        migrated["version"] = CURRENT_SCHEMA_VERSION
        migrated["compatible_version"] = legacy.get("compatible_version", MIN_COMPATIBLE_VERSION)

        # Optional fields - copy if present
        if "world_version" in legacy:
            migrated["world_version"] = legacy["world_version"]
        elif "data_version" in legacy:
            # Some legacy manifests use data_version (integer)
            # Convert to semver format: data_version 1 -> "0.0.1", 2 -> "0.0.2"
            migrated["world_version"] = f"0.0.{legacy['data_version']}"

        if "minimum_ap_version" in legacy:
            migrated["minimum_ap_version"] = legacy["minimum_ap_version"]

        if "maximum_ap_version" in legacy:
            migrated["maximum_ap_version"] = legacy["maximum_ap_version"]

        if "authors" in legacy:
            migrated["authors"] = legacy["authors"]

        if "description" in legacy:
            migrated["description"] = legacy["description"]

        if "license" in legacy:
            migrated["license"] = legacy["license"]

        if "homepage" in legacy:
            migrated["homepage"] = legacy["homepage"]

        if "repository" in legacy:
            migrated["repository"] = legacy["repository"]

        if "keywords" in legacy:
            migrated["keywords"] = legacy["keywords"]

        if "platforms" in legacy:
            migrated["platforms"] = legacy["platforms"]

        if "pure_python" in legacy:
            migrated["pure_python"] = legacy["pure_python"]

        if "vendored_dependencies" in legacy:
            migrated["vendored_dependencies"] = legacy["vendored_dependencies"]

        return migrated

    def test_migrate_minimal_manifest(self, legacy_manifest_minimal: dict):
        """Test migrating a minimal legacy manifest."""
        migrated = self._migrate_manifest(legacy_manifest_minimal)

        # Verify required fields are updated
        assert migrated["version"] == CURRENT_SCHEMA_VERSION
        assert migrated["game"] == "Legacy Game"
        assert migrated["compatible_version"] == 5

        # Validate against modern schema
        result = validate_manifest(migrated)
        assert result.valid, f"Validation errors: {result.errors}"

    def test_migrate_full_manifest(self, legacy_manifest_full: dict):
        """Test migrating a full legacy manifest with data_version."""
        migrated = self._migrate_manifest(legacy_manifest_full)

        # Verify data_version is converted to world_version (semver format)
        assert migrated["world_version"] == "0.0.1"  # data_version 1 -> "0.0.1"
        assert migrated["minimum_ap_version"] == "0.4.0"
        assert migrated["maximum_ap_version"] == "0.5.99"

        # Validate against modern schema
        result = validate_manifest(migrated)
        assert result.valid, f"Validation errors: {result.errors}"

    def test_migrate_manifest_with_extras(self, legacy_manifest_with_extras: dict):
        """Test migrating a manifest with extra metadata."""
        migrated = self._migrate_manifest(legacy_manifest_with_extras)

        # Verify all fields are preserved
        assert migrated["game"] == "Extra Legacy Game"
        assert migrated["world_version"] == "1.2.3"
        assert migrated["authors"] == ["Legacy Author"]
        assert migrated["description"] == "A legacy game description"
        assert migrated["license"] == "MIT"
        assert migrated["homepage"] == "https://example.com"
        assert migrated["repository"] == "https://github.com/example/repo"
        assert migrated["keywords"] == ["legacy", "test"]

        # Validate against modern schema
        result = validate_manifest(migrated)
        assert result.valid, f"Validation errors: {result.errors}"

    def test_build_from_migrated_manifest(
        self,
        sample_source_dir: Path,
        legacy_manifest_with_extras: dict,
        tmp_path: Path,
    ):
        """Test building an .apworld from a migrated manifest."""
        # Migrate the manifest
        migrated = self._migrate_manifest(legacy_manifest_with_extras)

        # Build using the migrated manifest values
        config = BuildConfig(
            name="legacy-game",
            version=migrated.get("world_version", "1.0.0"),
            game_name=migrated["game"],
            source_dir=sample_source_dir,
            description=migrated.get("description"),
            authors=migrated.get("authors", []),
            minimum_ap_version=migrated.get("minimum_ap_version"),
            maximum_ap_version=migrated.get("maximum_ap_version"),
            license=migrated.get("license"),
            keywords=migrated.get("keywords", []),
        )

        result = build_island(config, output_dir=tmp_path)

        # Verify the build succeeded
        assert result.path.exists()
        assert result.size > 0

        # Verify the manifest in the built .apworld
        with zipfile.ZipFile(result.path, "r") as zf:
            manifest_content = zf.read("legacy_game/archipelago.json").decode("utf-8")
            built_manifest = json.loads(manifest_content)

            assert built_manifest["game"] == "Extra Legacy Game"
            assert built_manifest["world_version"] == "1.2.3"
            assert built_manifest["authors"] == ["Legacy Author"]
            assert built_manifest["description"] == "A legacy game description"

    def test_migrated_manifest_defaults_applied(self, legacy_manifest_minimal: dict):
        """Test that defaults are applied to migrated manifests."""
        migrated = self._migrate_manifest(legacy_manifest_minimal)

        # Validate and get manifest with defaults
        result = validate_manifest(migrated)
        assert result.valid

        # Check that defaults were applied
        manifest_with_defaults = result.manifest
        assert manifest_with_defaults is not None
        assert manifest_with_defaults.get("pure_python") is True
        # Default platforms include all supported platforms
        assert manifest_with_defaults.get("platforms") == ["windows", "macos", "linux"]
        assert manifest_with_defaults.get("authors") == []
        assert manifest_with_defaults.get("keywords") == []

    def test_migration_preserves_compatibility(self, legacy_manifest_full: dict):
        """Test that migration preserves backward compatibility."""
        migrated = self._migrate_manifest(legacy_manifest_full)

        # The migrated manifest should still be loadable by older loaders
        # that only check for required fields
        assert "game" in migrated
        assert "version" in migrated
        assert "compatible_version" in migrated

        # The compatible_version should be preserved from the original
        assert migrated["compatible_version"] == legacy_manifest_full["compatible_version"]

    def test_end_to_end_migration_build_flow(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
    ):
        """Test the complete end-to-end migration and build flow."""
        # Create a legacy project structure
        project_dir = tmp_path / "legacy_project"
        project_dir.mkdir()

        # Copy sample source files
        src_dir = project_dir / "src" / "legacy_game"
        src_dir.mkdir(parents=True)
        shutil.copy(sample_source_dir / "__init__.py", src_dir / "__init__.py")
        shutil.copy(sample_source_dir / "world.py", src_dir / "world.py")

        # Create a legacy archipelago.json
        legacy_manifest = {
            "game": "Legacy Test Game",
            "version": 6,
            "compatible_version": 5,
            "data_version": 2,
            "minimum_ap_version": "0.4.0",
        }
        with open(project_dir / "archipelago.json", "w") as f:
            json.dump(legacy_manifest, f)

        # Step 1: Migrate the manifest
        migrated = self._migrate_manifest(legacy_manifest)

        # Step 2: Validate the migrated manifest
        result = validate_manifest(migrated)
        assert result.valid, f"Migration produced invalid manifest: {result.errors}"

        # Step 3: Build from the migrated project
        config = BuildConfig(
            name="legacy-test-game",
            version=migrated.get("world_version", "0.0.1"),
            game_name=migrated["game"],
            source_dir=src_dir,
            minimum_ap_version=migrated.get("minimum_ap_version"),
        )

        build_result = build_island(config, output_dir=tmp_path / "dist")

        # Step 4: Verify the built package
        assert build_result.path.exists()

        with zipfile.ZipFile(build_result.path, "r") as zf:
            # Check that all expected files are present
            names = zf.namelist()
            assert "legacy_test_game/__init__.py" in names
            assert "legacy_test_game/world.py" in names
            assert "legacy_test_game/archipelago.json" in names

            # Verify the manifest content
            manifest_content = zf.read("legacy_test_game/archipelago.json").decode("utf-8")
            built_manifest = json.loads(manifest_content)

            assert built_manifest["game"] == "Legacy Test Game"
            assert built_manifest["version"] == CURRENT_SCHEMA_VERSION
            assert built_manifest["minimum_ap_version"] == "0.4.0"
