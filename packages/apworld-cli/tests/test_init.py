# SPDX-License-Identifier: MIT
"""Tests for the apworld init command."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from apworld_cli.main import cli


class TestInitCommand:
    """Tests for apworld init command."""

    def test_init_creates_project_structure(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that init creates the expected directory structure."""
        result = cli_runner.invoke(cli, ["init", "my-game", "-o", str(tmp_path)])

        assert result.exit_code == 0
        assert "APWorld project created successfully" in result.output

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
    """Integration tests for apworld init command.

    These tests verify that the init command produces the expected file structure
    and that generated files have correct content.
    _Requirements: 4.2, 4.3_
    """

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
                "A test APWorld",
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

    def test_init_init_py_has_correct_content(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that __init__.py has correct imports and exports."""
        result = cli_runner.invoke(
            cli,
            [
                "init",
                "zelda-oot",
                "--game",
                "Zelda OOT",
                "-o",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0

        init_py = tmp_path / "zelda_oot" / "src" / "zelda_oot" / "__init__.py"
        content = init_py.read_text()

        # Verify imports and exports
        assert "from .world import ZeldaOotWorld" in content
        assert '__all__ = ["ZeldaOotWorld"]' in content
        assert "APWorld implementation for Zelda OOT." in content

        # Verify no template patterns remain
        assert "{{" not in content
        assert "}}" not in content

    def test_init_test_world_py_has_correct_content(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that test_world.py has correct test class names."""
        result = cli_runner.invoke(
            cli,
            [
                "init",
                "hollow-knight",
                "--game",
                "Hollow Knight",
                "-o",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0

        test_world = tmp_path / "hollow_knight" / "tests" / "test_world.py"
        content = test_world.read_text()

        # Verify test class names
        assert "class HollowKnightTestBase(WorldTestBase):" in content
        assert "class TestHollowKnightWorld(HollowKnightTestBase):" in content
        assert 'game = "Hollow Knight"' in content

        # Verify no template patterns remain
        assert "{{" not in content
        assert "}}" not in content

    def test_init_readme_has_correct_content(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that README.md has correct game name."""
        result = cli_runner.invoke(
            cli,
            [
                "init",
                "dark-souls",
                "--game",
                "Dark Souls",
                "-o",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0

        readme = tmp_path / "dark_souls" / "README.md"
        content = readme.read_text()

        # Verify game name substitution
        assert "# Dark Souls APWorld" in content
        assert "An Archipelago randomizer implementation for Dark Souls." in content

        # Verify no template patterns remain
        assert "{{" not in content
        assert "}}" not in content

    def test_init_docs_setup_has_correct_content(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that docs/setup_en.md has correct game name."""
        result = cli_runner.invoke(
            cli,
            [
                "init",
                "metroid-prime",
                "--game",
                "Metroid Prime",
                "-o",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0

        setup_doc = tmp_path / "metroid_prime" / "docs" / "setup_en.md"
        content = setup_doc.read_text()

        # Verify game name substitution
        assert "# Metroid Prime Setup Guide" in content

        # Verify no template patterns remain
        assert "{{" not in content
        assert "}}" not in content


class TestInitTemplateEnhancements:
    """Integration tests for init template enhancements.

    These tests verify that the enhanced template includes:
    - Comprehensive docstrings in Python modules
    - Example data entries in item_name_to_id and location_name_to_id
    - GitHub Actions workflow with valid YAML

    _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1_
    """

    def test_world_py_has_module_docstring(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that world.py has a module-level docstring.

        _Requirements: 1.1_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        world_py = tmp_path / "test_game" / "src" / "test_game" / "world.py"
        content = world_py.read_text()

        # Verify module-level docstring exists and contains key information
        assert '"""' in content
        assert "World implementation for Test Game" in content
        assert "https://github.com/ArchipelagoMW/Archipelago" in content

    def test_world_py_has_class_docstrings(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that world.py has class-level docstrings.

        _Requirements: 1.2_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        world_py = tmp_path / "test_game" / "src" / "test_game" / "world.py"
        content = world_py.read_text()

        # Verify WebWorld class docstring
        assert "Web configuration for Test Game" in content
        assert "theme:" in content.lower() or "theme" in content

        # Verify World class docstring
        assert "World implementation for Test Game" in content
        assert "Required Class Attributes:" in content
        assert "Key Methods to Implement:" in content

    def test_world_py_has_method_docstrings(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that world.py has method-level docstrings.

        _Requirements: 1.3_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        world_py = tmp_path / "test_game" / "src" / "test_game" / "world.py"
        content = world_py.read_text()

        # Verify method docstrings exist with Args/Returns sections
        assert "def create_item(self, name: str)" in content
        assert "Args:" in content
        assert "Returns:" in content
        assert "def create_regions(self)" in content
        assert "def create_items(self)" in content
        assert "def set_rules(self)" in content

    def test_init_py_has_module_docstring(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that __init__.py has a module-level docstring.

        _Requirements: 1.1_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        init_py = tmp_path / "test_game" / "src" / "test_game" / "__init__.py"
        content = init_py.read_text()

        # Verify module-level docstring exists
        assert '"""' in content
        assert "APWorld implementation for Test Game" in content
        assert "Package Structure:" in content
        assert "apworld build" in content

    def test_world_py_has_example_items(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that world.py has example entries in item_name_to_id.

        _Requirements: 2.1, 2.3_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        world_py = tmp_path / "test_game" / "src" / "test_game" / "world.py"
        content = world_py.read_text()

        # Verify example items exist
        assert "item_name_to_id" in content
        assert "Example Key" in content
        assert "Example Upgrade" in content
        assert "Example Coin" in content

        # Verify comments explaining item types
        assert "progression item" in content.lower()
        assert "useful item" in content.lower()
        assert "filler item" in content.lower()

        # Verify TODO comment for developers
        assert "TODO:" in content
        assert "Add your game's items here" in content

    def test_world_py_has_example_locations(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that world.py has example entries in location_name_to_id.

        _Requirements: 2.2, 2.3_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        world_py = tmp_path / "test_game" / "src" / "test_game" / "world.py"
        content = world_py.read_text()

        # Verify example locations exist
        assert "location_name_to_id" in content
        assert "Example Chest 1" in content
        assert "Example Chest 2" in content
        assert "Boss Reward" in content

        # Verify TODO comment for developers
        assert "Add your game's locations here" in content

    def test_world_py_has_base_id_explanation(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that world.py explains ID conventions.

        _Requirements: 2.3_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        world_py = tmp_path / "test_game" / "src" / "test_game" / "world.py"
        content = world_py.read_text()

        # Verify ID convention explanation
        assert "_BASE_ID" in content
        assert "0xABC00000" in content or "base" in content.lower()
        assert "unique" in content.lower()

    def test_github_workflow_exists(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that GitHub Actions workflow file is created.

        _Requirements: 3.1_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        workflow_path = tmp_path / "test_game" / ".github" / "workflows" / "ci.yml"
        assert workflow_path.exists(), "GitHub Actions workflow file not found"

    def test_github_workflow_is_valid_yaml(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that GitHub Actions workflow is valid YAML.

        _Requirements: 3.1_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        workflow_path = tmp_path / "test_game" / ".github" / "workflows" / "ci.yml"
        content = workflow_path.read_text()

        # Parse YAML to verify it's valid
        try:
            workflow = yaml.safe_load(content)
        except yaml.YAMLError as e:
            pytest.fail(f"GitHub Actions workflow is not valid YAML: {e}")

        # Verify basic workflow structure
        assert workflow is not None
        assert "name" in workflow
        # Note: YAML parses 'on' as True (boolean), so we check for True key
        # This is a known YAML quirk where 'on', 'yes', 'true' are all parsed as True
        assert True in workflow or "on" in workflow, "Workflow trigger ('on') not found"
        assert "jobs" in workflow

    def test_github_workflow_has_required_jobs(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that GitHub Actions workflow has required jobs.

        _Requirements: 3.1, 3.6, 4.1, 5.1_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        workflow_path = tmp_path / "test_game" / ".github" / "workflows" / "ci.yml"
        workflow = yaml.safe_load(workflow_path.read_text())

        jobs = workflow.get("jobs", {})

        # Verify required jobs exist
        assert "lint" in jobs, "lint job not found"
        assert "typecheck" in jobs, "typecheck job not found"
        assert "test" in jobs, "test job not found"
        assert "build" in jobs, "build job not found"
        assert "publish" in jobs, "publish job not found"

    def test_github_workflow_has_cross_platform_matrix(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that GitHub Actions workflow has cross-platform test matrix.

        _Requirements: 3.2, 3.3_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        workflow_path = tmp_path / "test_game" / ".github" / "workflows" / "ci.yml"
        workflow = yaml.safe_load(workflow_path.read_text())

        test_job = workflow.get("jobs", {}).get("test", {})
        strategy = test_job.get("strategy", {})
        matrix = strategy.get("matrix", {})

        # Verify OS matrix includes required platforms
        os_list = matrix.get("os", [])
        assert any("ubuntu" in os for os in os_list), "Linux not in OS matrix"
        assert any("macos" in os for os in os_list), "macOS not in OS matrix"
        assert any("windows" in os for os in os_list), "Windows not in OS matrix"

        # Verify Python version matrix
        python_versions = matrix.get("python-version", [])
        assert "3.11" in python_versions, "Python 3.11 not in matrix"
        assert "3.12" in python_versions, "Python 3.12 not in matrix"
        assert "3.13" in python_versions, "Python 3.13 not in matrix"

    def test_github_workflow_has_oidc_permissions(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that GitHub Actions workflow has OIDC permissions for trusted publishing.

        _Requirements: 5.2_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        workflow_path = tmp_path / "test_game" / ".github" / "workflows" / "ci.yml"
        workflow = yaml.safe_load(workflow_path.read_text())

        # Verify OIDC permissions are set
        permissions = workflow.get("permissions", {})
        assert "id-token" in permissions, "id-token permission not found"
        assert permissions["id-token"] == "write", "id-token should be 'write'"

    def test_github_workflow_no_template_patterns(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that GitHub Actions workflow has no unsubstituted template patterns.

        Note: GitHub Actions uses ${{ }} syntax for expressions, which is different
        from our Jinja2-style {{ }} template patterns. We only check for patterns
        that don't have the $ prefix.

        _Requirements: 3.1_
        """
        result = cli_runner.invoke(
            cli,
            ["init", "test-game", "--game", "Test Game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0

        workflow_path = tmp_path / "test_game" / ".github" / "workflows" / "ci.yml"
        content = workflow_path.read_text()

        # Check for unsubstituted Jinja2 template patterns (not GitHub Actions expressions)
        # GitHub Actions uses ${{ }} which is valid, but {{ }} without $ is our template
        import re

        # Find all {{ }} patterns that are NOT preceded by $
        # This regex finds {{ that is not preceded by $
        unsubstituted_patterns = re.findall(r"(?<!\$)\{\{[^}]+\}\}", content)
        assert (
            len(unsubstituted_patterns) == 0
        ), f"Unsubstituted template patterns found: {unsubstituted_patterns}"
