# SPDX-License-Identifier: MIT
"""Integration test: Build .apworld from sample project."""

import json
import zipfile
from pathlib import Path

import pytest

from apworld_build.apworld import build_apworld
from apworld_build.config import BuildConfig


class TestBuildSampleApworld:
    """Integration tests for building .apworld from sample project."""

    @pytest.fixture
    def sample_project_dir(self) -> Path:
        """Get the sample project directory."""
        return Path(__file__).parent / "sample_apworld"

    @pytest.fixture
    def sample_source_dir(self, sample_project_dir: Path) -> Path:
        """Get the sample source directory."""
        return sample_project_dir / "src" / "sample_game"

    def test_build_sample_apworld(self, sample_source_dir: Path, tmp_path: Path):
        """Test building .apworld from sample project."""
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
            description="A sample APWorld for testing",
            authors=["Test Author"],
            minimum_ap_version="0.5.0",
        )

        result = build_apworld(config, output_dir=tmp_path)

        # Verify the file was created
        assert result.path.exists()
        assert result.filename == "sample_game-1.0.0-py3-none-any.apworld"
        assert result.size > 0
        assert result.is_pure_python is True

    def test_sample_apworld_contents(self, sample_source_dir: Path, tmp_path: Path):
        """Test that the built .apworld contains expected files."""
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
        )

        result = build_apworld(config, output_dir=tmp_path)

        # Verify archive contents
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()

            # Check expected files
            assert "sample_game/__init__.py" in names
            assert "sample_game/world.py" in names
            assert "sample_game/archipelago.json" in names

    def test_sample_apworld_manifest(self, sample_source_dir: Path, tmp_path: Path):
        """Test that the manifest is correctly generated."""
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
            description="A sample APWorld for testing",
            authors=["Test Author"],
            minimum_ap_version="0.5.0",
        )

        result = build_apworld(config, output_dir=tmp_path)

        # Verify manifest
        with zipfile.ZipFile(result.path, "r") as zf:
            manifest_content = zf.read("sample_game/archipelago.json").decode("utf-8")
            manifest = json.loads(manifest_content)

            assert manifest["game"] == "Sample Game"
            assert manifest["world_version"] == "1.0.0"
            assert manifest["description"] == "A sample APWorld for testing"
            assert manifest["authors"] == ["Test Author"]
            assert manifest["minimum_ap_version"] == "0.5.0"
            assert manifest["pure_python"] is True
