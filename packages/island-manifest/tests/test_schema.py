# SPDX-License-Identifier: MIT
"""Tests for the manifest schema module."""

import pytest

from island_manifest.schema import (
    CURRENT_SCHEMA_VERSION,
    MANIFEST_DEFAULTS,
    MANIFEST_SCHEMA,
    MIN_COMPATIBLE_VERSION,
    PLATFORMS,
    get_default_values,
    get_manifest_schema,
)


class TestSchemaConstants:
    """Tests for schema constants."""

    def test_current_schema_version(self):
        """Current schema version should be 7."""
        assert CURRENT_SCHEMA_VERSION == 7

    def test_min_compatible_version(self):
        """Minimum compatible version should be 5."""
        assert MIN_COMPATIBLE_VERSION == 5

    def test_platforms_list(self):
        """Platforms should include all major OS."""
        assert "windows" in PLATFORMS
        assert "macos" in PLATFORMS
        assert "linux" in PLATFORMS
        assert len(PLATFORMS) == 3


class TestManifestSchema:
    """Tests for the manifest schema structure."""

    def test_schema_has_required_fields(self):
        """Schema should require game, version, and compatible_version."""
        assert "required" in MANIFEST_SCHEMA
        assert "game" in MANIFEST_SCHEMA["required"]
        assert "version" in MANIFEST_SCHEMA["required"]
        assert "compatible_version" in MANIFEST_SCHEMA["required"]

    def test_schema_has_all_properties(self):
        """Schema should define all expected properties."""
        props = MANIFEST_SCHEMA["properties"]
        expected = [
            "game",
            "version",
            "compatible_version",
            "world_version",
            "minimum_ap_version",
            "maximum_ap_version",
            "authors",
            "description",
            "license",
            "homepage",
            "repository",
            "keywords",
            "vendored_dependencies",
            "platforms",
            "pure_python",
            "entry_points",
            "external_dependencies",
        ]
        for field in expected:
            assert field in props, f"Missing property: {field}"

    def test_external_dependencies_field(self):
        """External dependencies field should be nullable array."""
        ext_deps_schema = MANIFEST_SCHEMA["properties"]["external_dependencies"]
        assert ext_deps_schema["type"] == ["array", "null"]
        assert "items" in ext_deps_schema
        assert ext_deps_schema["items"]["type"] == "object"
        assert "Reserved" in ext_deps_schema["description"]

    def test_game_field_constraints(self):
        """Game field should have length constraints."""
        game_schema = MANIFEST_SCHEMA["properties"]["game"]
        assert game_schema["type"] == "string"
        assert game_schema["minLength"] == 1
        assert game_schema["maxLength"] == 100

    def test_version_field_is_const(self):
        """Version field should be a constant value."""
        version_schema = MANIFEST_SCHEMA["properties"]["version"]
        assert version_schema["const"] == CURRENT_SCHEMA_VERSION

    def test_world_version_has_semver_pattern(self):
        """World version should have semver pattern validation."""
        world_version_schema = MANIFEST_SCHEMA["properties"]["world_version"]
        assert "pattern" in world_version_schema

    def test_platforms_enum_values(self):
        """Platforms should be restricted to enum values."""
        platforms_schema = MANIFEST_SCHEMA["properties"]["platforms"]
        assert platforms_schema["items"]["enum"] == PLATFORMS


class TestDefaultValues:
    """Tests for default value handling."""

    def test_defaults_include_all_optional_fields(self):
        """Defaults should be defined for all optional fields."""
        expected_defaults = [
            "authors",
            "description",
            "license",
            "keywords",
            "vendored_dependencies",
            "platforms",
            "pure_python",
            "external_dependencies",
        ]
        for field in expected_defaults:
            assert field in MANIFEST_DEFAULTS, f"Missing default for: {field}"

    def test_default_external_dependencies_is_none(self):
        """Default external_dependencies should be None (reserved for future)."""
        assert MANIFEST_DEFAULTS["external_dependencies"] is None

    def test_default_platforms_includes_all(self):
        """Default platforms should include all supported platforms."""
        assert MANIFEST_DEFAULTS["platforms"] == ["windows", "macos", "linux"]

    def test_default_pure_python_is_true(self):
        """Default pure_python should be True."""
        assert MANIFEST_DEFAULTS["pure_python"] is True

    def test_default_authors_is_empty_list(self):
        """Default authors should be empty list."""
        assert MANIFEST_DEFAULTS["authors"] == []

    def test_default_vendored_dependencies_is_empty_dict(self):
        """Default vendored_dependencies should be empty dict."""
        assert MANIFEST_DEFAULTS["vendored_dependencies"] == {}


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_manifest_schema_returns_copy(self):
        """get_manifest_schema should return a copy."""
        schema1 = get_manifest_schema()
        schema2 = get_manifest_schema()
        assert schema1 is not schema2
        assert schema1 == schema2

    def test_get_default_values_returns_copy(self):
        """get_default_values should return a copy."""
        defaults1 = get_default_values()
        defaults2 = get_default_values()
        assert defaults1 is not defaults2
        assert defaults1 == defaults2
