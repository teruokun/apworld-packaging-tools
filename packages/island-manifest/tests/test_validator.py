# SPDX-License-Identifier: MIT
"""Tests for the manifest validator module."""

import pytest

from island_manifest.validator import (
    ManifestValidationError,
    validate_manifest,
    validate_manifest_strict,
    ValidationErrorDetail,
    ValidationResult,
)


class TestValidateManifest:
    """Tests for validate_manifest function."""

    def test_valid_minimal_manifest(self):
        """Minimal valid manifest should pass validation."""
        manifest = {
            "game": "Test Game",
            "version": 7,
            "compatible_version": 7,
            "entry_points": {"ap-island": {"test_game": "test_game.world:TestWorld"}},
        }
        result = validate_manifest(manifest)
        assert result.valid is True
        assert result.errors == []
        assert result.manifest is not None

    def test_valid_full_manifest(self):
        """Full manifest with all fields should pass validation."""
        manifest = {
            "game": "Pokemon Emerald",
            "version": 7,
            "compatible_version": 6,
            "world_version": "2.1.0",
            "minimum_ap_version": "0.5.0",
            "maximum_ap_version": "0.6.99",
            "authors": ["Zunawe"],
            "description": "Pokemon Emerald randomizer",
            "license": "MIT",
            "homepage": "https://example.com",
            "repository": "https://github.com/example/repo",
            "keywords": ["pokemon", "gba"],
            "platforms": ["windows", "macos", "linux"],
            "pure_python": True,
            "entry_points": {
                "ap-island": {"pokemon_emerald": "pokemon_emerald.world:PokemonEmeraldWorld"}
            },
        }
        result = validate_manifest(manifest)
        assert result.valid is True
        assert result.manifest is not None

    def test_applies_defaults_for_missing_optional_fields(self):
        """Missing optional fields should get default values."""
        manifest = {
            "game": "Test Game",
            "version": 7,
            "compatible_version": 7,
            "entry_points": {"ap-island": {"test_game": "test_game.world:TestWorld"}},
        }
        result = validate_manifest(manifest)
        assert result.valid is True
        assert result.manifest["authors"] == []
        assert result.manifest["description"] == ""
        assert result.manifest["platforms"] == ["windows", "macos", "linux"]
        assert result.manifest["pure_python"] is True

    def test_missing_required_game_field(self):
        """Missing game field should fail validation."""
        manifest = {
            "version": 7,
            "compatible_version": 7,
        }
        result = validate_manifest(manifest)
        assert result.valid is False
        assert len(result.errors) >= 1
        assert any("game" in e.message.lower() for e in result.errors)

    def test_missing_required_version_field(self):
        """Missing version field should fail validation."""
        manifest = {
            "game": "Test",
            "compatible_version": 7,
        }
        result = validate_manifest(manifest)
        assert result.valid is False
        assert any("version" in e.message.lower() for e in result.errors)

    def test_wrong_version_value(self):
        """Wrong version value should fail validation."""
        manifest = {
            "game": "Test",
            "version": 6,  # Should be 7
            "compatible_version": 6,
        }
        result = validate_manifest(manifest)
        assert result.valid is False

    def test_invalid_game_type(self):
        """Non-string game should fail validation."""
        manifest = {
            "game": 123,
            "version": 7,
            "compatible_version": 7,
        }
        result = validate_manifest(manifest)
        assert result.valid is False
        assert any("string" in e.message.lower() for e in result.errors)

    def test_empty_game_string(self):
        """Empty game string should fail validation."""
        manifest = {
            "game": "",
            "version": 7,
            "compatible_version": 7,
        }
        result = validate_manifest(manifest)
        assert result.valid is False

    def test_game_too_long(self):
        """Game name over 100 chars should fail validation."""
        manifest = {
            "game": "A" * 101,
            "version": 7,
            "compatible_version": 7,
        }
        result = validate_manifest(manifest)
        assert result.valid is False

    def test_invalid_semver_world_version(self):
        """Invalid semver in world_version should fail validation."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 7,
            "world_version": "not-a-version",
        }
        result = validate_manifest(manifest)
        assert result.valid is False
        assert any("pattern" in e.message.lower() for e in result.errors)

    def test_valid_semver_with_prerelease(self):
        """Semver with prerelease should pass validation."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 7,
            "world_version": "1.0.0-alpha.1",
            "entry_points": {"ap-island": {"test": "test.world:TestWorld"}},
        }
        result = validate_manifest(manifest)
        assert result.valid is True

    def test_valid_semver_with_build_metadata(self):
        """Semver with build metadata should pass validation."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 7,
            "world_version": "1.0.0+build.123",
            "entry_points": {"ap-island": {"test": "test.world:TestWorld"}},
        }
        result = validate_manifest(manifest)
        assert result.valid is True

    def test_invalid_platform_value(self):
        """Invalid platform value should fail validation."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 7,
            "platforms": ["windows", "invalid_os"],
            "entry_points": {"ap-island": {"test": "test.world:TestWorld"}},
        }
        result = validate_manifest(manifest)
        assert result.valid is False
        assert any(
            "enum" in e.message.lower() or "one of" in e.message.lower() for e in result.errors
        )

    def test_homepage_accepts_uri_string(self):
        """Homepage field accepts URI strings (format validation is advisory)."""
        # Note: JSON Schema format validation is advisory by default
        # The schema declares format: uri but doesn't enforce strict validation
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 7,
            "homepage": "https://example.com",
            "entry_points": {"ap-island": {"test": "test.world:TestWorld"}},
        }
        result = validate_manifest(manifest)
        assert result.valid is True

    def test_compatible_version_below_minimum(self):
        """Compatible version below minimum should fail validation."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 4,  # Below minimum of 5
        }
        result = validate_manifest(manifest)
        assert result.valid is False

    def test_compatible_version_above_maximum(self):
        """Compatible version above maximum should fail validation."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 8,  # Above maximum of 7
        }
        result = validate_manifest(manifest)
        assert result.valid is False

    def test_non_dict_manifest(self):
        """Non-dict manifest should fail validation."""
        result = validate_manifest("not a dict")
        assert result.valid is False
        assert len(result.errors) == 1
        assert "dictionary" in result.errors[0].message.lower()

    def test_none_manifest(self):
        """None manifest should fail validation."""
        result = validate_manifest(None)
        assert result.valid is False

    def test_authors_must_be_array(self):
        """Authors must be an array."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 7,
            "authors": "single author",
        }
        result = validate_manifest(manifest)
        assert result.valid is False

    def test_keywords_must_be_strings(self):
        """Keywords must be strings."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 7,
            "keywords": [123, 456],
            "entry_points": {"ap-island": {"test": "test.world:TestWorld"}},
        }
        result = validate_manifest(manifest)
        assert result.valid is False


class TestValidateManifestStrict:
    """Tests for validate_manifest_strict function."""

    def test_valid_manifest_returns_dict(self):
        """Valid manifest should return processed dict."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 7,
            "entry_points": {"ap-island": {"test": "test.world:TestWorld"}},
        }
        result = validate_manifest_strict(manifest)
        assert isinstance(result, dict)
        assert result["game"] == "Test"
        assert result["pure_python"] is True  # Default applied

    def test_invalid_manifest_raises_exception(self):
        """Invalid manifest should raise ManifestValidationError."""
        manifest = {"game": ""}  # Missing required fields
        with pytest.raises(ManifestValidationError) as exc_info:
            validate_manifest_strict(manifest)
        assert len(exc_info.value.errors) > 0


class TestValidationErrorDetail:
    """Tests for ValidationErrorDetail dataclass."""

    def test_error_detail_fields(self):
        """ValidationErrorDetail should have expected fields."""
        error = ValidationErrorDetail(
            field="world_version",
            message="Invalid format",
            value="bad-version",
        )
        assert error.field == "world_version"
        assert error.message == "Invalid format"
        assert error.value == "bad-version"

    def test_error_detail_optional_value(self):
        """Value field should be optional."""
        error = ValidationErrorDetail(field="game", message="Required")
        assert error.value is None


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Valid result should have valid=True and manifest."""
        result = ValidationResult(valid=True, manifest={"game": "Test"})
        assert result.valid is True
        assert result.errors == []
        assert result.manifest == {"game": "Test"}

    def test_invalid_result(self):
        """Invalid result should have valid=False and errors."""
        errors = [ValidationErrorDetail(field="game", message="Required")]
        result = ValidationResult(valid=False, errors=errors)
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.manifest is None
