# SPDX-License-Identifier: MIT
"""Tests for the register command."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from island_cli.main import cli
from island_cli.commands.register import (
    _compute_sha256,
    _extract_platform_tag,
    _validate_checksum_format,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_project_with_entry_points(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory with pyproject.toml including entry points."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create pyproject.toml with entry points
    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text(
        """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-game"
version = "1.0.0"
description = "Test Island Package"
authors = [{name = "Test Author"}]
keywords = ["test", "archipelago"]

[project.urls]
Homepage = "https://example.com"
Repository = "https://github.com/test/test-game"

[project.entry-points.ap-island]
"Test Game" = "test_game:World"

[tool.island]
game = "Test Game"
minimum_ap_version = "0.5.0"
maximum_ap_version = "0.6.0"
"""
    )

    # Create source directory
    src_dir = project_dir / "src" / "test_game"
    src_dir.mkdir(parents=True)

    # Create __init__.py
    init_file = src_dir / "__init__.py"
    init_file.write_text('"""Test Game Island Package."""\n')

    yield project_dir


@pytest.fixture
def temp_distribution(tmp_path: Path) -> Path:
    """Create a temporary distribution file."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    # Create a fake .island file
    island_file = dist_dir / "test_game-1.0.0-py3-none-any.island"
    island_file.write_bytes(b"fake island content for testing")

    return island_file


class TestComputeSha256:
    """Tests for _compute_sha256 function."""

    def test_compute_sha256_returns_correct_hash(self, tmp_path: Path) -> None:
        """Test that SHA256 is computed correctly."""
        test_file = tmp_path / "test.txt"
        content = b"test content"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        result = _compute_sha256(test_file)

        assert result == expected
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_sha256_empty_file(self, tmp_path: Path) -> None:
        """Test SHA256 of empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        expected = hashlib.sha256(b"").hexdigest()
        result = _compute_sha256(test_file)

        assert result == expected


class TestExtractPlatformTag:
    """Tests for _extract_platform_tag function."""

    def test_extract_platform_tag_island_file(self) -> None:
        """Test extracting platform tag from .island filename."""
        filename = "my_game-1.0.0-py3-none-any.island"
        result = _extract_platform_tag(filename)
        assert result == "py3-none-any"

    def test_extract_platform_tag_specific_platform(self) -> None:
        """Test extracting platform tag with specific platform."""
        filename = "my_game-1.0.0-cp311-cp311-win_amd64.island"
        result = _extract_platform_tag(filename)
        assert result == "cp311-cp311-win_amd64"

    def test_extract_platform_tag_source_dist(self) -> None:
        """Test extracting platform tag from source distribution."""
        filename = "my_game-1.0.0.tar.gz"
        result = _extract_platform_tag(filename)
        assert result == "source"

    def test_extract_platform_tag_fallback(self) -> None:
        """Test fallback for unknown format."""
        filename = "unknown_format.zip"
        result = _extract_platform_tag(filename)
        assert result == "py3-none-any"


class TestValidateChecksumFormat:
    """Tests for _validate_checksum_format function."""

    def test_valid_checksum(self) -> None:
        """Test valid SHA256 checksum."""
        valid = "a" * 64
        assert _validate_checksum_format(valid) is True

    def test_valid_checksum_mixed_hex(self) -> None:
        """Test valid SHA256 with mixed hex characters."""
        valid = "0123456789abcdef" * 4
        assert _validate_checksum_format(valid) is True

    def test_invalid_checksum_too_short(self) -> None:
        """Test invalid checksum that's too short."""
        invalid = "a" * 63
        assert _validate_checksum_format(invalid) is False

    def test_invalid_checksum_too_long(self) -> None:
        """Test invalid checksum that's too long."""
        invalid = "a" * 65
        assert _validate_checksum_format(invalid) is False

    def test_invalid_checksum_non_hex(self) -> None:
        """Test invalid checksum with non-hex characters."""
        invalid = "g" * 64
        assert _validate_checksum_format(invalid) is False

    def test_valid_checksum_uppercase_converted(self) -> None:
        """Test that uppercase is accepted (converted to lowercase)."""
        valid = "A" * 64
        assert _validate_checksum_format(valid) is True


class TestRegisterCommand:
    """Tests for the register command."""

    def test_register_requires_url(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
    ) -> None:
        """Test that register command requires at least one URL."""
        result = cli_runner.invoke(
            cli,
            ["register", "--dry-run"],
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        assert "At least one --url is required" in result.output

    def test_register_requires_https(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
        temp_distribution: Path,
    ) -> None:
        """Test that register command requires HTTPS URLs."""
        result = cli_runner.invoke(
            cli,
            [
                "-C",
                str(temp_project_with_entry_points),
                "register",
                "--url",
                "http://example.com/file.island",
                "--file",
                str(temp_distribution),
                "--dry-run",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        assert "URL must use HTTPS" in result.output

    def test_register_requires_checksum_or_file(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
    ) -> None:
        """Test that register command requires checksum or file."""
        result = cli_runner.invoke(
            cli,
            [
                "-C",
                str(temp_project_with_entry_points),
                "register",
                "--url",
                "https://example.com/file.island",
                "--dry-run",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        assert "No checksum provided" in result.output

    def test_register_validates_checksum_format(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
    ) -> None:
        """Test that register command validates checksum format."""
        result = cli_runner.invoke(
            cli,
            [
                "-C",
                str(temp_project_with_entry_points),
                "register",
                "--url",
                "https://example.com/file.island",
                "--checksum",
                "invalid",
                "--dry-run",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        assert "Invalid checksum format" in result.output

    def test_register_dry_run_with_file(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
        temp_distribution: Path,
    ) -> None:
        """Test register command dry run with local file."""
        result = cli_runner.invoke(
            cli,
            [
                "-C",
                str(temp_project_with_entry_points),
                "register",
                "--url",
                "https://github.com/test/repo/releases/download/v1.0.0/test_game-1.0.0-py3-none-any.island",
                "--file",
                str(temp_distribution),
                "--dry-run",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "test-game" in result.output
        assert "1.0.0" in result.output
        assert "Test Game" in result.output

        # Verify the payload contains expected fields
        assert '"name": "test-game"' in result.output
        assert '"version": "1.0.0"' in result.output
        assert '"game": "Test Game"' in result.output
        assert '"minimum_ap_version": "0.5.0"' in result.output

    def test_register_dry_run_with_explicit_checksum(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
        temp_distribution: Path,
    ) -> None:
        """Test register command dry run with explicit checksum."""
        # Compute the actual checksum
        checksum = _compute_sha256(temp_distribution)
        size = temp_distribution.stat().st_size

        result = cli_runner.invoke(
            cli,
            [
                "-C",
                str(temp_project_with_entry_points),
                "register",
                "--url",
                "https://github.com/test/repo/releases/download/v1.0.0/test_game-1.0.0-py3-none-any.island",
                "--checksum",
                checksum,
                "--file",
                str(temp_distribution),  # Still need file for size
                "--dry-run",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert checksum in result.output

    def test_register_checksum_mismatch(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
        temp_distribution: Path,
    ) -> None:
        """Test register command detects checksum mismatch."""
        wrong_checksum = "a" * 64

        result = cli_runner.invoke(
            cli,
            [
                "-C",
                str(temp_project_with_entry_points),
                "register",
                "--url",
                "https://github.com/test/repo/releases/download/v1.0.0/test_game-1.0.0-py3-none-any.island",
                "--checksum",
                wrong_checksum,
                "--file",
                str(temp_distribution),
                "--dry-run",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        assert "Checksum mismatch" in result.output

    def test_register_requires_auth_without_dry_run(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
        temp_distribution: Path,
    ) -> None:
        """Test register command requires authentication without dry-run."""
        result = cli_runner.invoke(
            cli,
            [
                "-C",
                str(temp_project_with_entry_points),
                "register",
                "--url",
                "https://github.com/test/repo/releases/download/v1.0.0/test_game-1.0.0-py3-none-any.island",
                "--file",
                str(temp_distribution),
            ],
            catch_exceptions=False,
            env={"ISLAND_TOKEN": ""},  # Clear any existing token
        )

        assert result.exit_code == 1
        assert "Authentication required" in result.output

    def test_register_multiple_distributions(
        self,
        cli_runner: CliRunner,
        temp_project_with_entry_points: Path,
        tmp_path: Path,
    ) -> None:
        """Test register command with multiple distributions."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()

        # Create island file
        island_file = dist_dir / "test_game-1.0.0-py3-none-any.island"
        island_file.write_bytes(b"island content")

        # Create source distribution
        sdist_file = dist_dir / "test_game-1.0.0.tar.gz"
        sdist_file.write_bytes(b"source content")

        result = cli_runner.invoke(
            cli,
            [
                "-C",
                str(temp_project_with_entry_points),
                "register",
                "--url",
                "https://github.com/test/repo/releases/download/v1.0.0/test_game-1.0.0-py3-none-any.island",
                "--file",
                str(island_file),
                "--url",
                "https://github.com/test/repo/releases/download/v1.0.0/test_game-1.0.0.tar.gz",
                "--file",
                str(sdist_file),
                "--dry-run",
            ],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "Distributions: 2" in result.output
        assert "test_game-1.0.0-py3-none-any.island" in result.output
        assert "test_game-1.0.0.tar.gz" in result.output
