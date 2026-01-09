# SPDX-License-Identifier: MIT
"""Tests for the apworld migrate command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apworld_cli.main import cli


class TestMigrateCommand:
    """Tests for apworld migrate command."""

    def test_migrate_legacy_manifest(self, cli_runner: CliRunner, legacy_project: Path) -> None:
        """Test migrating a legacy manifest to modern schema."""
        manifest_path = legacy_project / "archipelago.json"

        result = cli_runner.invoke(cli, ["migrate", "-i", str(manifest_path)])

        assert result.exit_code == 0
        assert "Migration complete" in result.output

        # Check the migrated manifest
        with open(manifest_path) as f:
            migrated = json.load(f)

        assert migrated["version"] == 7  # Current schema version
        assert migrated["game"] == "Legacy Game"
        assert migrated["compatible_version"] == 5

    def test_migrate_generates_pyproject(self, cli_runner: CliRunner, legacy_project: Path) -> None:
        """Test that migrate can generate pyproject.toml."""
        manifest_path = legacy_project / "archipelago.json"

        result = cli_runner.invoke(
            cli, ["migrate", "-i", str(manifest_path), "--generate-pyproject"]
        )

        assert result.exit_code == 0

        pyproject_path = legacy_project / "pyproject.toml"
        assert pyproject_path.exists()

        content = pyproject_path.read_text()
        assert 'game = "Legacy Game"' in content
        assert 'version = "0.5.0"' in content

    def test_migrate_dry_run(self, cli_runner: CliRunner, legacy_project: Path) -> None:
        """Test migrate dry run doesn't write files."""
        manifest_path = legacy_project / "archipelago.json"
        original_content = manifest_path.read_text()

        result = cli_runner.invoke(cli, ["migrate", "-i", str(manifest_path), "--dry-run"])

        assert result.exit_code == 0
        assert "Dry run" in result.output

        # File should be unchanged
        assert manifest_path.read_text() == original_content

    def test_migrate_already_modern(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test migrate warns when manifest is already modern."""
        manifest_path = tmp_path / "archipelago.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "game": "Modern Game",
                    "version": 7,
                    "compatible_version": 5,
                }
            )
        )

        result = cli_runner.invoke(cli, ["migrate", "-i", str(manifest_path)])

        assert result.exit_code == 0
        assert "already uses modern schema" in result.output

    def test_migrate_custom_output(
        self, cli_runner: CliRunner, legacy_project: Path, tmp_path: Path
    ) -> None:
        """Test migrate with custom output path."""
        manifest_path = legacy_project / "archipelago.json"
        output_path = tmp_path / "migrated.json"

        result = cli_runner.invoke(
            cli, ["migrate", "-i", str(manifest_path), "-o", str(output_path)]
        )

        assert result.exit_code == 0
        assert output_path.exists()

        with open(output_path) as f:
            migrated = json.load(f)

        assert migrated["version"] == 7

    def test_migrate_preserves_optional_fields(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that migrate preserves optional fields from legacy manifest."""
        manifest_path = tmp_path / "archipelago.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "game": "Full Game",
                    "version": 6,
                    "compatible_version": 5,
                    "world_version": "2.0.0",
                    "authors": ["Author One", "Author Two"],
                    "description": "A full description",
                    "license": "MIT",
                    "homepage": "https://example.com",
                    "repository": "https://github.com/example/repo",
                    "keywords": ["keyword1", "keyword2"],
                    "minimum_ap_version": "0.4.0",
                    "maximum_ap_version": "0.6.0",
                }
            )
        )

        result = cli_runner.invoke(cli, ["migrate", "-i", str(manifest_path), "--force"])

        assert result.exit_code == 0

        with open(manifest_path) as f:
            migrated = json.load(f)

        assert migrated["authors"] == ["Author One", "Author Two"]
        assert migrated["description"] == "A full description"
        assert migrated["license"] == "MIT"
        assert migrated["homepage"] == "https://example.com"
        assert migrated["repository"] == "https://github.com/example/repo"
        assert migrated["keywords"] == ["keyword1", "keyword2"]
        assert migrated["minimum_ap_version"] == "0.4.0"
        assert migrated["maximum_ap_version"] == "0.6.0"
