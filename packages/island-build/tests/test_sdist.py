# SPDX-License-Identifier: MIT
"""Tests for source distribution builder module."""

import tarfile
import pytest
from pathlib import Path

from island_build.sdist import (
    SdistError,
    build_sdist_from_directory,
    collect_source_files,
)


class TestCollectSourceFiles:
    """Tests for collect_source_files function."""

    def test_collects_python_files(self, tmp_path):
        # Create test files
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "utils.py").write_text("# utils")
        (tmp_path / "data.txt").write_text("data")

        files = collect_source_files(tmp_path)
        file_names = [f.name for f in files]

        assert "main.py" in file_names
        assert "utils.py" in file_names

    def test_collects_nested_files(self, tmp_path):
        # Create nested structure
        subdir = tmp_path / "subpackage"
        subdir.mkdir()
        (subdir / "__init__.py").write_text("")
        (subdir / "module.py").write_text("# module")

        files = collect_source_files(tmp_path)
        file_paths = [str(f) for f in files]

        assert any("subpackage" in p and "module.py" in p for p in file_paths)

    def test_excludes_pycache(self, tmp_path):
        # Create __pycache__ directory
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-311.pyc").write_bytes(b"")
        (tmp_path / "main.py").write_text("# main")

        files = collect_source_files(tmp_path)
        file_paths = [str(f) for f in files]

        assert not any("__pycache__" in p for p in file_paths)
        assert not any(".pyc" in p for p in file_paths)

    def test_includes_metadata_files(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]")
        (tmp_path / "README.md").write_text("# README")
        (tmp_path / "LICENSE").write_text("MIT")

        files = collect_source_files(tmp_path)
        file_names = [f.name for f in files]

        assert "pyproject.toml" in file_names
        assert "README.md" in file_names
        assert "LICENSE" in file_names

    def test_custom_exclude_patterns(self, tmp_path):
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "test_main.py").write_text("# test")

        files = collect_source_files(
            tmp_path,
            exclude_patterns=["test_*.py"],
        )
        file_names = [f.name for f in files]

        assert "main.py" in file_names
        assert "test_main.py" not in file_names


class TestBuildSdistFromDirectory:
    """Tests for build_sdist_from_directory function."""

    def test_creates_tarball(self, tmp_path):
        # Create source directory
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        (src_dir / "pyproject.toml").write_text("[project]")

        output_dir = tmp_path / "dist"

        result = build_sdist_from_directory(
            source_dir=src_dir,
            name="my-game",
            version="1.0.0",
            output_dir=output_dir,
        )

        assert result.path.exists()
        assert result.filename == "my_game-1.0.0.tar.gz"
        assert result.size > 0
        assert len(result.files_included) > 0

    def test_tarball_structure(self, tmp_path):
        # Create source directory
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")

        output_dir = tmp_path / "dist"

        result = build_sdist_from_directory(
            source_dir=src_dir,
            name="my-game",
            version="1.0.0",
            output_dir=output_dir,
        )

        # Verify tarball contents
        with tarfile.open(result.path, "r:gz") as tar:
            names = tar.getnames()
            # Should have prefix: my_game-1.0.0/
            assert any("my_game-1.0.0/main.py" in n for n in names)

    def test_empty_source_raises(self, tmp_path):
        src_dir = tmp_path / "empty"
        src_dir.mkdir()
        output_dir = tmp_path / "dist"

        with pytest.raises(SdistError, match="No source files found"):
            build_sdist_from_directory(
                source_dir=src_dir,
                name="my-game",
                version="1.0.0",
                output_dir=output_dir,
            )

    def test_nonexistent_source_raises(self, tmp_path):
        with pytest.raises(SdistError, match="does not exist"):
            build_sdist_from_directory(
                source_dir=tmp_path / "nonexistent",
                name="my-game",
                version="1.0.0",
                output_dir=tmp_path / "dist",
            )
