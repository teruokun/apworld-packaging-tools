# SPDX-License-Identifier: MIT
"""Tests for build configuration module."""

import json
import pytest
from pathlib import Path

from island_build.config import (
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
                "island": {
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
                "island": {
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
                "island": {
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
        manifest_path = tmp_path / "island.json"
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
        manifest_path = tmp_path / "island.json"
        manifest_path.write_text(json.dumps(manifest))

        with pytest.raises(BuildConfigError, match="Missing required field: game"):
            BuildConfig.from_manifest(manifest_path, source_dir=tmp_path)

    def test_from_manifest_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            BuildConfig.from_manifest(tmp_path / "nonexistent.json", source_dir=tmp_path)


# Property-based tests using Hypothesis
from hypothesis import given, strategies as st, settings


# Strategies for generating valid configuration values
valid_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_"),
    min_size=1,
    max_size=50,
).filter(lambda s: s[0].isalpha() and not s.startswith("-") and not s.startswith("_"))

valid_version_strategy = st.tuples(
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}")

valid_game_name_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 -_"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() and s[0].isalpha())

valid_ap_version_strategy = st.tuples(
    st.integers(min_value=0, max_value=9),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}")

vendor_exclude_strategy = st.lists(
    st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
        min_size=1,
        max_size=30,
    ).filter(lambda s: s[0].isalpha()),
    min_size=0,
    max_size=5,
)


class TestConfigPropertyBased:
    """Property-based tests for configuration handling.

    Feature: island-format-migration, Property 7: Configuration section recognition
    Validates: Requirements 7.3
    """

    @given(
        name=valid_name_strategy,
        version=valid_version_strategy,
        game_name=valid_game_name_strategy,
        min_ap_version=valid_ap_version_strategy,
        max_ap_version=st.one_of(st.none(), valid_ap_version_strategy),
        vendor_exclude=vendor_exclude_strategy,
    )
    @settings(max_examples=100)
    def test_tool_island_config_applied(
        self,
        name: str,
        version: str,
        game_name: str,
        min_ap_version: str,
        max_ap_version: str | None,
        vendor_exclude: list[str],
    ):
        """Property 7: Configuration section recognition

        For any project with [tool.island] configuration, the build tool SHALL
        read and apply the island-specific settings (game name, AP version bounds,
        vendor exclusions).

        Feature: island-format-migration, Property 7: Configuration section recognition
        Validates: Requirements 7.3
        """
        # Build a pyproject.toml dictionary with [tool.island] configuration
        pyproject = {
            "project": {
                "name": name,
                "version": version,
            },
            "tool": {
                "island": {
                    "game": game_name,
                    "minimum_ap_version": min_ap_version,
                }
            },
        }

        # Add optional maximum_ap_version if provided
        if max_ap_version is not None:
            pyproject["tool"]["island"]["maximum_ap_version"] = max_ap_version

        # Add vendor.exclude if non-empty
        if vendor_exclude:
            pyproject["tool"]["island"]["vendor"] = {"exclude": vendor_exclude}

        # Parse the configuration
        config = BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))

        # Verify all [tool.island] settings are correctly applied
        assert config.game_name == game_name, "Game name from [tool.island] not applied"
        assert config.minimum_ap_version == min_ap_version, "minimum_ap_version not applied"

        if max_ap_version is not None:
            assert config.maximum_ap_version == max_ap_version, "maximum_ap_version not applied"
        else:
            assert (
                config.maximum_ap_version == ""
            ), "maximum_ap_version should be empty when not set"

        assert config.vendor_exclude == vendor_exclude, "vendor.exclude not applied"

        # Verify project fields are also correctly read
        assert config.name == name
        assert config.version == version

    @given(
        name=valid_name_strategy,
        version=valid_version_strategy,
    )
    @settings(max_examples=100)
    def test_game_name_derived_when_not_specified(
        self,
        name: str,
        version: str,
    ):
        """When [tool.island].game is not specified, game name should be derived from project name.

        Feature: island-format-migration, Property 7: Configuration section recognition
        Validates: Requirements 7.3
        """
        # Build a pyproject.toml dictionary WITHOUT [tool.island].game
        pyproject = {
            "project": {
                "name": name,
                "version": version,
            },
            # No [tool.island] section at all
        }

        # Parse the configuration
        config = BuildConfig.from_pyproject_dict(pyproject, source_dir=Path("."))

        # Game name should be derived from project name (title-cased, with - and _ replaced by spaces)
        expected_game_name = name.replace("-", " ").replace("_", " ").title()
        assert config.game_name == expected_game_name, (
            f"Game name should be derived from project name: expected '{expected_game_name}', "
            f"got '{config.game_name}'"
        )
