# SPDX-License-Identifier: MIT
"""Tests for the apworld build command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from apworld_cli.main import cli


class TestBuildCommand:
    """Tests for apworld build command."""

    def test_build_creates_apworld(self, cli_runner: CliRunner, temp_project: Path) -> None:
        """Test that build creates an .apworld file."""
        result = cli_runner.invoke(cli, ["-C", str(temp_project), "build", "--no-vendor"])

        assert result.exit_code == 0
        assert "Build complete" in result.output

        dist_dir = temp_project / "dist"
        apworld_files = list(dist_dir.glob("*.apworld"))
        assert len(apworld_files) == 1
        assert "test_game" in apworld_files[0].name

    def test_build_creates_sdist(self, cli_runner: CliRunner, temp_project: Path) -> None:
        """Test that build --sdist creates a source distribution."""
        result = cli_runner.invoke(
            cli, ["-C", str(temp_project), "build", "--sdist", "--no-vendor"]
        )

        assert result.exit_code == 0

        dist_dir = temp_project / "dist"
        sdist_files = list(dist_dir.glob("*.tar.gz"))
        assert len(sdist_files) == 1

    def test_build_custom_output_dir(
        self, cli_runner: CliRunner, temp_project: Path, tmp_path: Path
    ) -> None:
        """Test build with custom output directory."""
        output_dir = tmp_path / "custom_dist"

        result = cli_runner.invoke(
            cli,
            ["-C", str(temp_project), "build", "-o", str(output_dir), "--no-vendor"],
        )

        assert result.exit_code == 0
        assert output_dir.exists()
        assert len(list(output_dir.glob("*.apworld"))) == 1

    def test_build_no_project_files(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test build fails gracefully with no project files."""
        result = cli_runner.invoke(cli, ["-C", str(tmp_path), "build"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_build_verbose_output(self, cli_runner: CliRunner, temp_project: Path) -> None:
        """Test build with verbose output."""
        result = cli_runner.invoke(cli, ["-v", "-C", str(temp_project), "build", "--no-vendor"])

        assert result.exit_code == 0
        assert "Package:" in result.output or "Game:" in result.output
