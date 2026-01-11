# SPDX-License-Identifier: MIT
"""Tests for the island init command."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from island_cli.main import cli


class TestInitCommand:
    """Tests for island init command."""

    def test_init_creates_project_structure(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that init creates the expected directory structure."""
        result = cli_runner.invoke(cli, ["init", "my-game", "-o", str(tmp_path)])

        assert result.exit_code == 0
        assert "Island project created successfully" in result.output

        project_dir = tmp_path / "my_game"
        assert project_dir.exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / "LICENSE").exists()
        assert (project_dir / "src" / "my_game" / "__init__.py").exists()
        assert (project_dir / "src" / "my_game" / "world.py").exists()
        assert (project_dir / "tests" / "__init__.py").exists()
        assert (project_dir / "tests" / "test_world.py").exists()

    def test_init_with_custom_game_name(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test init with custom game display name."""
        result = cli_runner.invoke(
            cli,
            ["init", "pokemon-emerald", "--game", "Pokemon Emerald", "-o", str(tmp_path)],
        )

        assert result.exit_code == 0

        project_dir = tmp_path / "pokemon_emerald"
        pyproject = project_dir / "pyproject.toml"
        content = pyproject.read_text()

        assert 'game = "Pokemon Emerald"' in content
        assert 'name = "pokemon-emerald"' in content

    def test_init_with_author(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test init with custom author name."""
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--author", "Test Developer", "-o", str(tmp_path)],
        )

        assert result.exit_code == 0

        project_dir = tmp_path / "test_game"
        pyproject = project_dir / "pyproject.toml"
        content = pyproject.read_text()

        assert 'name = "Test Developer"' in content

    def test_init_refuses_existing_directory(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that init refuses to overwrite existing directory."""
        # Create the directory first
        existing = tmp_path / "existing_game"
        existing.mkdir()

        result = cli_runner.invoke(cli, ["init", "existing-game", "-o", str(tmp_path)])

        assert result.exit_code == 1
        assert "Directory already exists" in result.output

    def test_init_force_overwrites(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that init --force overwrites existing directory."""
        # Create the directory first
        existing = tmp_path / "existing_game"
        existing.mkdir()
        (existing / "old_file.txt").write_text("old content")

        result = cli_runner.invoke(cli, ["init", "existing-game", "-o", str(tmp_path), "--force"])

        assert result.exit_code == 0
        assert (existing / "pyproject.toml").exists()

    def test_init_normalizes_package_name(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that init normalizes package names correctly."""
        result = cli_runner.invoke(cli, ["init", "My Cool Game!", "-o", str(tmp_path)])

        assert result.exit_code == 0

        # Should normalize to my_cool_game
        project_dir = tmp_path / "my_cool_game"
        assert project_dir.exists()


class TestInitIntegration:
    """Integration tests for island init command."""

    def test_init_produces_complete_file_structure(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that init produces the complete expected file structure."""
        result = cli_runner.invoke(
            cli,
            [
                "init",
                "test-game",
                "--game",
                "Test Game",
                "--author",
                "Test Author",
                "--description",
                "A test Island package",
                "-o",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0

        project_dir = tmp_path / "test_game"

        # Verify all expected files exist
        expected_files = [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "src/test_game/__init__.py",
            "src/test_game/world.py",
            "tests/__init__.py",
            "tests/test_world.py",
            "docs/setup_en.md",
        ]

        for file_path in expected_files:
            full_path = project_dir / file_path
            assert full_path.exists(), f"Expected file not found: {file_path}"

    def test_init_pyproject_has_correct_content(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that pyproject.toml has correct variable substitutions."""
        result = cli_runner.invoke(
            cli,
            [
                "init",
                "pokemon-emerald",
                "--game",
                "Pokemon Emerald",
                "--author",
                "Game Dev",
                "--description",
                "Pokemon Emerald randomizer",
                "-o",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0

        pyproject = tmp_path / "pokemon_emerald" / "pyproject.toml"
        content = pyproject.read_text()

        # Verify all template variables were substituted
        assert 'name = "pokemon-emerald"' in content
        assert 'description = "Pokemon Emerald randomizer"' in content
        assert 'name = "Game Dev"' in content
        assert '"pokemon-emerald"' in content  # game_lower in keywords
        assert 'game = "Pokemon Emerald"' in content
        assert 'packages = ["src/pokemon_emerald"]' in content

        # Verify no template patterns remain
        assert "{{" not in content
        assert "}}" not in content

    def test_init_world_py_has_correct_content(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that world.py has correct class names and game references."""
        result = cli_runner.invoke(
            cli,
            [
                "init",
                "super-mario",
                "--game",
                "Super Mario",
                "--author",
                "Nintendo Fan",
                "-o",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0

        world_py = tmp_path / "super_mario" / "src" / "super_mario" / "world.py"
        content = world_py.read_text()

        # Verify class names are correctly generated
        assert "class SuperMarioWebWorld(WebWorld):" in content
        assert "class SuperMarioWorld(World):" in content
        assert 'game = "Super Mario"' in content
        assert 'authors=["Nintendo Fan"]' in content

        # Verify no template patterns remain
        assert "{{" not in content
        assert "}}" not in content
