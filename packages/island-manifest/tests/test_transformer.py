# SPDX-License-Identifier: MIT
"""Tests for the pyproject.toml transformer module."""

import tempfile
from pathlib import Path

import pytest

from island_manifest.transformer import (
    ManifestTransformError,
    TransformConfig,
    transform_pyproject,
    transform_pyproject_dict,
)


class TestTransformPyprojectDict:
    """Tests for transform_pyproject_dict function."""

    def test_minimal_pyproject(self):
        """Minimal pyproject with just name should work."""
        pyproject = {
            "project": {
                "name": "test-game",
            }
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["game"] == "Test Game"  # Title case conversion
        assert manifest["version"] == 7
        assert manifest["compatible_version"] == 5

    def test_game_from_tool_island(self):
        """Game name from tool.island takes precedence."""
        pyproject = {
            "project": {"name": "test-game"},
            "tool": {"island": {"game": "Custom Game Name"}},
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["game"] == "Custom Game Name"

    def test_full_pyproject(self):
        """Full pyproject with all fields should transform correctly."""
        pyproject = {
            "project": {
                "name": "pokemon-emerald",
                "version": "2.1.0",
                "description": "Pokemon Emerald randomizer",
                "license": {"text": "MIT"},
                "authors": [{"name": "Zunawe", "email": "test@example.com"}],
                "keywords": ["pokemon", "gba", "emerald"],
                "urls": {
                    "Homepage": "https://example.com",
                    "Repository": "https://github.com/example/repo",
                },
            },
            "tool": {
                "island": {
                    "game": "Pokemon Emerald",
                    "minimum_ap_version": "0.5.0",
                    "maximum_ap_version": "0.6.99",
                    "platforms": ["windows", "macos"],
                    "pure_python": True,
                }
            },
        }
        manifest = transform_pyproject_dict(pyproject)

        assert manifest["game"] == "Pokemon Emerald"
        assert manifest["world_version"] == "2.1.0"
        assert manifest["description"] == "Pokemon Emerald randomizer"
        assert manifest["license"] == "MIT"
        assert manifest["authors"] == ["Zunawe"]
        assert manifest["keywords"] == ["pokemon", "gba", "emerald"]
        assert manifest["homepage"] == "https://example.com"
        assert manifest["repository"] == "https://github.com/example/repo"
        assert manifest["minimum_ap_version"] == "0.5.0"
        assert manifest["maximum_ap_version"] == "0.6.99"
        assert manifest["platforms"] == ["windows", "macos"]
        assert manifest["pure_python"] is True

    def test_missing_game_and_name_raises_error(self):
        """Missing both game and name should raise error."""
        pyproject = {"project": {}}
        with pytest.raises(ManifestTransformError) as exc_info:
            transform_pyproject_dict(pyproject)
        assert "game" in str(exc_info.value).lower()

    def test_empty_pyproject_raises_error(self):
        """Empty pyproject should raise error."""
        with pytest.raises(ManifestTransformError):
            transform_pyproject_dict({})

    def test_applies_defaults(self):
        """Missing optional fields should get defaults."""
        pyproject = {"project": {"name": "test"}}
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["authors"] == []
        assert manifest["description"] == ""
        assert manifest["platforms"] == ["windows", "macos", "linux"]
        assert manifest["pure_python"] is True

    def test_author_as_string(self):
        """Author as plain string should work."""
        pyproject = {
            "project": {
                "name": "test",
                "authors": ["John Doe"],
            }
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["authors"] == ["John Doe"]

    def test_author_as_dict_with_name(self):
        """Author as dict with name should extract name."""
        pyproject = {
            "project": {
                "name": "test",
                "authors": [{"name": "Jane Doe", "email": "jane@example.com"}],
            }
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["authors"] == ["Jane Doe"]

    def test_author_dict_without_name_skipped(self):
        """Author dict without name should be skipped."""
        pyproject = {
            "project": {
                "name": "test",
                "authors": [{"email": "test@example.com"}],
            }
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["authors"] == []

    def test_license_as_string(self):
        """License as plain string should work."""
        pyproject = {
            "project": {
                "name": "test",
                "license": "MIT",
            }
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["license"] == "MIT"

    def test_license_as_dict_with_text(self):
        """License as dict with text should extract text."""
        pyproject = {
            "project": {
                "name": "test",
                "license": {"text": "Apache-2.0"},
            }
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["license"] == "Apache-2.0"

    def test_urls_lowercase_keys(self):
        """URLs with lowercase keys should work."""
        pyproject = {
            "project": {
                "name": "test",
                "urls": {
                    "homepage": "https://example.com",
                    "repository": "https://github.com/test",
                },
            }
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["homepage"] == "https://example.com"
        assert manifest["repository"] == "https://github.com/test"

    def test_urls_source_as_repository(self):
        """Source URL should be used as repository."""
        pyproject = {
            "project": {
                "name": "test",
                "urls": {"Source": "https://github.com/test"},
            }
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["repository"] == "https://github.com/test"

    def test_custom_transform_config(self):
        """Custom TransformConfig should be respected."""
        pyproject = {"project": {"name": "test"}}
        config = TransformConfig(schema_version=7, compatible_version=6)
        manifest = transform_pyproject_dict(pyproject, config)
        assert manifest["version"] == 7
        assert manifest["compatible_version"] == 6

    def test_name_with_underscores(self):
        """Name with underscores should convert to title case."""
        pyproject = {"project": {"name": "my_cool_game"}}
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["game"] == "My Cool Game"

    def test_pure_python_false(self):
        """pure_python=False should be preserved."""
        pyproject = {
            "project": {"name": "test"},
            "tool": {"island": {"pure_python": False}},
        }
        manifest = transform_pyproject_dict(pyproject)
        assert manifest["pure_python"] is False


class TestTransformPyproject:
    """Tests for transform_pyproject function (file-based)."""

    def test_file_not_found(self):
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            transform_pyproject("/nonexistent/pyproject.toml")

    def test_valid_toml_file(self):
        """Valid TOML file should be parsed correctly."""
        toml_content = """
[project]
name = "test-game"
version = "1.0.0"
description = "A test game"

[tool.island]
game = "Test Game"
minimum_ap_version = "0.5.0"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            manifest = transform_pyproject(f.name)

        assert manifest["game"] == "Test Game"
        assert manifest["world_version"] == "1.0.0"
        assert manifest["description"] == "A test game"
        assert manifest["minimum_ap_version"] == "0.5.0"

    def test_invalid_toml_syntax(self):
        """Invalid TOML syntax should raise ManifestTransformError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("invalid toml [[[")
            f.flush()
            with pytest.raises(ManifestTransformError) as exc_info:
                transform_pyproject(f.name)
            assert "toml" in str(exc_info.value).lower()

    def test_path_object(self):
        """Path object should work as input."""
        toml_content = """
[project]
name = "path-test"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            manifest = transform_pyproject(Path(f.name))

        assert manifest["game"] == "Path Test"


class TestTransformConfig:
    """Tests for TransformConfig dataclass."""

    def test_default_values(self):
        """Default config should have expected values."""
        config = TransformConfig()
        assert config.schema_version == 7
        assert config.compatible_version == 5

    def test_custom_values(self):
        """Custom values should be stored."""
        config = TransformConfig(schema_version=8, compatible_version=6)
        assert config.schema_version == 8
        assert config.compatible_version == 6
