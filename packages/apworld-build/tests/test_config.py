# SPDX-License-Identifier: MIT
"""Tests for build configuration module."""

import json
import pytest
from pathlib import Path

from apworld_build.config import (
    BuildConfig,
    BuildConfigError,
    DEFAULT_SCHEMA_VERSION,
    MIN_COMPATIBLE_VERSION,
)


class TestBuildConfig:
    """Tests for BuildConfig class."""

    def test_normalized_name(self):
        config = BuildConfig(
            name="Pokemon-Emerald",
            version="1.0.0",
            game_name="Pokemon Emerald",
            source_dir=Path("."),
        )
        assert config.normalized_name == "pokemon_emerald"

    def test_to_manifest(self):
        config = BuildConfig(
            name="pokemon-emerald",
            version="1.0.0",
            game_name="Pokemon Emerald",
            source_dir=Path("."),
            description="A test game",
            authors=["Test Author"],
            minimum_ap_version="0.5.0",
        )
        manifest = config.to_manifest()

        assert manifest["game"] == "Pokemon Emerald"
        assert manifest["version"] == DEFAULT_SCHEMA_VERSION
        assert manifest["compatible_version"] == MIN_COMPATIBLE_VERSION
        assert manifest["world_version"] == "1.0.0"
        assert manifest["description"] == "A test game"
        assert manifest["authors"] == ["Test Author"]
        assert manifest["minimum_ap_version"] == "0.5.0"
        assert manifest["pure_python"] is True


class TestBuildConfigFromPyproject:
    """Tests for BuildConfig.from_pyproject_dict method."""

    def test_minimal_config(self):
        pyproject = {
            "project": {
                "name": "my-game",
                "version": "1.0.0",
            }
        }
        config = BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))

        assert config.name == "my-game"
        assert config.version == "1.0.0"
        assert config.game_name == "My Game"  # Derived from name

    def test_full_config(self):
        pyproject = {
            "project": {
                "name": "pokemon-emerald",
                "version": "2.1.0",
                "description": "Pokemon Emerald randomizer",
                "authors": [{"name": "Zunawe", "email": "test@example.com"}],
                "license": {"text": "MIT"},
                "keywords": ["pokemon", "gba"],
                "dependencies": ["pyyaml>=6.0"],
                "urls": {
                    "Homepage": "https://example.com",
                    "Repository": "https://github.com/example/repo",
                },
            },
            "tool": {
                "apworld": {
                    "game": "Pokemon Emerald",
                    "minimum_ap_version": "0.5.0",
                    "maximum_ap_version": "0.6.99",
                    "platforms": ["windows", "macos", "linux"],
                }
            },
        }
        config = BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))

        assert config.name == "pokemon-emerald"
        assert config.version == "2.1.0"
        assert config.game_name == "Pokemon Emerald"
        assert config.description == "Pokemon Emerald randomizer"
        assert config.authors == ["Zunawe"]
        assert config.license == "MIT"
        assert config.keywords == ["pokemon", "gba"]
        assert config.dependencies == ["pyyaml>=6.0"]
        assert config.homepage == "https://example.com"
        assert config.repository == "https://github.com/example/repo"
        assert config.minimum_ap_version == "0.5.0"
        assert config.maximum_ap_version == "0.6.99"
        assert config.platforms == ["windows", "macos", "linux"]

    def test_missing_name_raises(self):
        pyproject = {"project": {"version": "1.0.0"}}
        with pytest.raises(BuildConfigError, match="Missing required field.*name"):
            BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))

    def test_missing_version_raises(self):
        pyproject = {"project": {"name": "my-game"}}
        with pytest.raises(BuildConfigError, match="Missing required field.*version"):
            BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))

    def test_author_string_format(self):
        pyproject = {
            "project": {
                "name": "my-game",
                "version": "1.0.0",
                "authors": ["Author One", "Author Two"],
            }
        }
        config = BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))
        assert config.authors == ["Author One", "Author Two"]

    def test_license_string_format(self):
        pyproject = {
            "project": {
                "name": "my-game",
                "version": "1.0.0",
                "license": "MIT",
            }
        }
        config = BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))
        assert config.license == "MIT"

    def test_build_patterns(self):
        pyproject = {
            "project": {
                "name": "my-game",
                "version": "1.0.0",
            },
            "tool": {
                "apworld": {
                    "build": {
                        "include": ["*.py", "data/*.json"],
                        "exclude": ["tests/*"],
                    }
                }
            },
        }
        config = BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))
        assert config.include_patterns == ["*.py", "data/*.json"]
        assert config.exclude_patterns == ["tests/*"]

    def test_vendor_exclude(self):
        pyproject = {
            "project": {
                "name": "my-game",
                "version": "1.0.0",
            },
            "tool": {
                "apworld": {
                    "vendor": {
                        "exclude": ["typing_extensions", "colorama"],
                    }
                }
            },
        }
        config = BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))
        assert config.vendor_exclude == ["typing_extensions", "colorama"]


class TestBuildConfigFromManifest:
    """Tests for BuildConfig.from_manifest method (legacy mode)."""

    def test_from_manifest(self, tmp_path):
        manifest = {
            "game": "Pokemon Emerald",
            "version": 7,
            "compatible_version": 5,
            "world_version": "1.0.0",
            "description": "A test game",
            "authors": ["Test Author"],
        }
        manifest_path = tmp_path / "archipelago.json"
        manifest_path.write_text(json.dumps(manifest))

        config = BuildConfig.from_manifest(manifest_path, source_dir=tmp_path)

        assert config.name == "pokemon-emerald"
        assert config.version == "1.0.0"
        assert config.game_name == "Pokemon Emerald"
        assert config.description == "A test game"
        assert config.authors == ["Test Author"]
        assert config.schema_version == 7
        assert config.compatible_version == 5

    def test_from_manifest_missing_game_raises(self, tmp_path):
        manifest = {"version": 7}
        manifest_path = tmp_path / "archipelago.json"
        manifest_path.write_text(json.dumps(manifest))

        with pytest.raises(BuildConfigError, match="Missing required field: game"):
            BuildConfig.from_manifest(manifest_path, source_dir=tmp_path)

    def test_from_manifest_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            BuildConfig.from_manifest(tmp_path / "nonexistent.json", source_dir=tmp_path)
