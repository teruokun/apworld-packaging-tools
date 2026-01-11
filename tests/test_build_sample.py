# SPDX-License-Identifier: MIT
"""Integration test: Build .island from sample project.

This test verifies the island format build functionality:
- Filename format: {name}-{version}-{python}-{abi}-{platform}.island
- Wheel structure: dist-info directory with WHEEL, METADATA, RECORD, island.json
- Entry points: ap-island entry points in entry_points.txt
"""

import json
import zipfile
from pathlib import Path

import pytest

from island_build.config import BuildConfig
from island_build.island import build_island


class TestBuildSampleIsland:
    """Integration tests for building .island from sample project."""

    @pytest.fixture
    def sample_project_dir(self) -> Path:
        """Get the sample project directory."""
        return Path(__file__).parent / "sample_island"

    @pytest.fixture
    def sample_source_dir(self, sample_project_dir: Path) -> Path:
        """Get the sample source directory."""
        return sample_project_dir / "src" / "sample_game"

    def test_build_sample_island_filename(self, sample_source_dir: Path, tmp_path: Path):
        """Test building .island produces correct filename format.

        Validates: Requirements 1.1, 2.2, 5.1, 5.2, 5.3
        """
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
            description="A sample Island for testing",
            authors=["Test Author"],
            minimum_ap_version="0.5.0",
        )

        result = build_island(config, output_dir=tmp_path)

        # Verify the file was created with .island extension
        assert result.path.exists()
        assert result.filename == "sample_game-1.0.0-py3-none-any.island"
        assert result.filename.endswith(".island")
        assert result.size > 0
        assert result.is_pure_python is True

        # Verify platform tag
        assert str(result.platform_tag) == "py3-none-any"

    def test_sample_island_wheel_structure(self, sample_source_dir: Path, tmp_path: Path):
        """Test that the built .island contains wheel structure.

        Validates: Requirements 2.1, 2.3, 2.4, 2.5
        """
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
        )

        result = build_island(config, output_dir=tmp_path)

        # Verify archive contents
        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()

            # Check source files
            assert "sample_game/__init__.py" in names
            assert "sample_game/world.py" in names

            # Check dist-info directory with wheel metadata
            dist_info = "sample_game-1.0.0.dist-info"
            assert f"{dist_info}/WHEEL" in names
            assert f"{dist_info}/METADATA" in names
            assert f"{dist_info}/RECORD" in names
            assert f"{dist_info}/island.json" in names

    def test_sample_island_wheel_metadata(self, sample_source_dir: Path, tmp_path: Path):
        """Test that WHEEL file is PEP 427 compliant.

        Validates: Requirements 2.1, 2.3
        """
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
        )

        result = build_island(config, output_dir=tmp_path)

        with zipfile.ZipFile(result.path, "r") as zf:
            wheel_content = zf.read("sample_game-1.0.0.dist-info/WHEEL").decode("utf-8")

            # Verify PEP 427 required fields
            assert "Wheel-Version: 1.0" in wheel_content
            assert "Generator: island-build" in wheel_content
            assert "Root-Is-Purelib: true" in wheel_content
            assert "Tag: py3-none-any" in wheel_content

    def test_sample_island_package_metadata(self, sample_source_dir: Path, tmp_path: Path):
        """Test that METADATA file is PEP 566 compliant.

        Validates: Requirements 2.4
        """
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
            description="A sample Island for testing",
            authors=["Test Author"],
        )

        result = build_island(config, output_dir=tmp_path)

        with zipfile.ZipFile(result.path, "r") as zf:
            metadata_content = zf.read("sample_game-1.0.0.dist-info/METADATA").decode("utf-8")

            # Verify PEP 566 required fields
            assert "Metadata-Version: 2.1" in metadata_content
            assert "Name: sample-game" in metadata_content
            assert "Version: 1.0.0" in metadata_content
            assert "Summary: A sample Island for testing" in metadata_content
            assert "Author: Test Author" in metadata_content

            # Verify NO Requires-Dist (dependencies are vendored)
            assert "Requires-Dist" not in metadata_content

    def test_sample_island_manifest(self, sample_source_dir: Path, tmp_path: Path):
        """Test that the island.json manifest is correctly generated.

        Validates: Requirements 2.1
        """
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
            description="A sample Island for testing",
            authors=["Test Author"],
            minimum_ap_version="0.5.0",
        )

        result = build_island(config, output_dir=tmp_path)

        # Verify manifest in dist-info
        with zipfile.ZipFile(result.path, "r") as zf:
            manifest_content = zf.read("sample_game-1.0.0.dist-info/island.json").decode("utf-8")
            manifest = json.loads(manifest_content)

            assert manifest["game"] == "Sample Game"
            assert manifest["world_version"] == "1.0.0"
            assert manifest["description"] == "A sample Island for testing"
            assert manifest["authors"] == ["Test Author"]
            assert manifest["minimum_ap_version"] == "0.5.0"
            assert manifest["pure_python"] is True

    def test_sample_island_with_entry_points(self, sample_source_dir: Path, tmp_path: Path):
        """Test building .island with ap-island entry points.

        Validates: Requirements 3.1, 3.2
        """
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
        )

        # Provide entry points
        entry_points = {"ap-island": {"sample_game": "sample_game.world:SampleWorld"}}

        result = build_island(config, output_dir=tmp_path, entry_points=entry_points)

        with zipfile.ZipFile(result.path, "r") as zf:
            names = zf.namelist()

            # Check entry_points.txt exists
            assert "sample_game-1.0.0.dist-info/entry_points.txt" in names

            # Verify entry points content
            ep_content = zf.read("sample_game-1.0.0.dist-info/entry_points.txt").decode("utf-8")
            assert "[ap-island]" in ep_content
            assert "sample_game = sample_game.world:SampleWorld" in ep_content

            # Verify entry points in manifest
            manifest_content = zf.read("sample_game-1.0.0.dist-info/island.json").decode("utf-8")
            manifest = json.loads(manifest_content)
            assert "entry_points" in manifest
            assert "ap-island" in manifest["entry_points"]
            assert (
                manifest["entry_points"]["ap-island"]["sample_game"]
                == "sample_game.world:SampleWorld"
            )

    def test_sample_island_record_integrity(self, sample_source_dir: Path, tmp_path: Path):
        """Test that RECORD file lists all files with checksums.

        Validates: Requirements 2.5
        """
        import base64
        import hashlib

        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
        )

        result = build_island(config, output_dir=tmp_path)

        with zipfile.ZipFile(result.path, "r") as zf:
            record_content = zf.read("sample_game-1.0.0.dist-info/RECORD").decode("utf-8")
            record_lines = [line for line in record_content.strip().split("\n") if line]

            # Parse RECORD entries
            record_entries = {}
            for line in record_lines:
                parts = line.split(",")
                path = parts[0]
                hash_str = parts[1] if len(parts) > 1 else ""
                record_entries[path] = hash_str

            # Verify all files in archive are in RECORD
            for name in zf.namelist():
                assert name in record_entries, f"File {name} not in RECORD"

            # Verify RECORD itself has no hash (per PEP 427)
            record_path = "sample_game-1.0.0.dist-info/RECORD"
            assert record_entries[record_path] == "", "RECORD should have empty hash"

            # Verify at least one file hash is correct
            init_path = "sample_game/__init__.py"
            init_content = zf.read(init_path)
            sha256 = hashlib.sha256(init_content)
            expected_hash = "sha256=" + base64.urlsafe_b64encode(sha256.digest()).rstrip(
                b"="
            ).decode("ascii")
            assert record_entries[init_path] == expected_hash, "Hash mismatch for __init__.py"
