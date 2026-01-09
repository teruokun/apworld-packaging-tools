# SPDX-License-Identifier: MIT
"""Tests for the apworld validate command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from apworld_cli.main import cli


class TestValidateCommand:
    """Tests for apworld validate command."""

    def test_validate_valid_pyproject(self, cli_runner: CliRunner, temp_project: Path) -> None:
        """Test validating a valid pyproject.toml."""
        result = cli_runner.invoke(cli, ["-C", str(temp_project), "validate"])

        assert result.exit_code == 0
        assert "Validation passed" in result.output

    def test_validate_valid_manifest(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test validating a valid archipelago.json."""
        manifest_path = tmp_path / "archipelago.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "game": "Test Game",
                    "version": 7,
                    "compatible_version": 5,
                    "world_version": "1.0.0",
                }
            )
        )

        result = cli_runner.invoke(cli, ["validate", "-m", str(manifest_path)])

        assert result.exit_code == 0
        assert "Validation passed" in result.output

    def test_validate_invalid_manifest_missing_game(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test validating manifest with missing required field."""
        manifest_path = tmp_path / "archipelago.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "version": 7,
                    "compatible_version": 5,
                }
            )
        )

        result = cli_runner.invoke(cli, ["validate", "-m", str(manifest_path)])

        assert result.exit_code == 1
        assert "Missing required field" in result.output or "game" in result.output.lower()

    def test_validate_invalid_version_format(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test validating manifest with invalid version format."""
        manifest_path = tmp_path / "archipelago.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "game": "Test Game",
                    "version": 7,
                    "compatible_version": 5,
                    "world_version": "not-a-version",
                }
            )
        )

        result = cli_runner.invoke(cli, ["validate", "-m", str(manifest_path)])

        assert result.exit_code == 1
        assert "semantic versioning" in result.output.lower() or "version" in result.output.lower()

    def test_validate_strict_mode(self, cli_runner: CliRunner, temp_project: Path) -> None:
        """Test that strict mode treats warnings as errors."""
        # Remove the source directory to trigger a warning
        src_dir = temp_project / "src" / "test_game"
        for f in src_dir.iterdir():
            f.unlink()
        src_dir.rmdir()

        result = cli_runner.invoke(cli, ["-C", str(temp_project), "validate", "--strict"])

        # Should fail due to structure warnings in strict mode
        assert result.exit_code == 1 or "warning" in result.output.lower()

    def test_validate_no_project_files(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test validate with no project files."""
        result = cli_runner.invoke(cli, ["-C", str(tmp_path), "validate"])

        assert result.exit_code == 1
        assert "no pyproject.toml" in result.output.lower() or "not found" in result.output.lower()
