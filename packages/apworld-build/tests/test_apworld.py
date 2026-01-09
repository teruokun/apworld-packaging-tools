# SPDX-License-Identifier: MIT
"""Tests for APWorld binary distribution builder module."""

import json
import zipfile
import pytest
from pathlib import Path

from apworld_build.apworld import (
    ApworldError,
    build_apworld,
)
from apworld_build.config import BuildConfig
from apworld_build.filename import UNIVERSAL_TAG, PlatformTag


class TestBuildApworld:
    """Tests for build_apworld function."""

    def test_creates_apworld_file(self, tmp_path):
        # Create source directory
        src_dir = tmp_path / "src" / "my_game"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("# My Game APWorld")
        (src_dir / "world.py").write_text("class MyWorld: pass")

        output_dir = tmp_path / "dist"

        config = BuildConfig(
            name="my-game",
            version="1.0.0",
            game_name="My Game",
            source_dir=src_dir,
        )

        result = build_apworld(config, output_dir=output_dir)

        assert result.path.exists()
        assert result.filename == "my_game-1.0.0-py3-none-any.apworld"
        assert result.size > 0
        assert result.is_pure_python is True
        assert result.platform_tag == UNIVERSAL_TAG

    def test_apworld_contains_manifest(self, tmp_path):
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

        result = build_apworld(config, output_dir=output_dir)

        # Verify manifest in archive
        with zipfile.ZipFile(result.path, "r") as zf:
            manifest_path = "my_game/archipelago.json"
            assert manifest_path in zf.namelist()

            manifest_content = zf.read(manifest_path).decode("utf-8")
            manifest = json.loads(manifest_content)

            assert manifest["game"] == "My Game"
            assert manifest["world_version"] == "1.0.0"
            assert manifest["description"] == "Test game"
            assert manifest["authors"] == ["Test Author"]
            assert manifest["pure_python"] is True

    def test_apworld_structure(self, tmp_path):
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

        result = build_apworld(config, output_dir=output_dir)

        # Verify structure
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()
            assert "my_game/__init__.py" in names
            assert "my_game/world.py" in names
            assert "my_game/data/__init__.py" in names
            assert "my_game/data/items.py" in names
            assert "my_game/archipelago.json" in names

    def test_apworld_with_vendor_dir(self, tmp_path):
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

        result = build_apworld(config, output_dir=output_dir, vendor_dir=vendor_dir)

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

        with pytest.raises(ApworldError, match="does not exist"):
            build_apworld(config, output_dir=tmp_path / "dist")

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
        result = build_apworld(config, output_dir=output_dir, platform_tag=custom_tag)

        assert result.filename == "my_game-1.0.0-cp311-cp311-win_amd64.apworld"
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

        result = build_apworld(config, output_dir=output_dir)

        assert result.manifest["minimum_ap_version"] == "0.5.0"
        assert result.manifest["maximum_ap_version"] == "0.6.99"
