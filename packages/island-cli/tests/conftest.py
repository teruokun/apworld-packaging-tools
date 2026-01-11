# SPDX-License-Identifier: MIT
"""Pytest configuration and fixtures for CLI tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory with pyproject.toml."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create pyproject.toml
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

[tool.island]
game = "Test Game"
minimum_ap_version = "0.5.0"
"""
    )

    # Create source directory
    src_dir = project_dir / "src" / "test_game"
    src_dir.mkdir(parents=True)

    # Create __init__.py
    init_file = src_dir / "__init__.py"
    init_file.write_text('"""Test Game Island Package."""\n')

    # Create world.py
    world_file = src_dir / "world.py"
    world_file.write_text(
        '''"""Test Game World."""

class TestGameWorld:
    game = "Test Game"
'''
    )

    yield project_dir


@pytest.fixture
def legacy_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project with legacy archipelago.json."""
    project_dir = tmp_path / "legacy_project"
    project_dir.mkdir()

    # Create legacy archipelago.json
    manifest = project_dir / "archipelago.json"
    manifest.write_text(
        json.dumps(
            {
                "game": "Legacy Game",
                "version": 6,
                "compatible_version": 5,
                "world_version": "0.5.0",
                "authors": ["Legacy Author"],
                "description": "A legacy Island package",
            },
            indent=2,
        )
    )

    # Create source directory
    src_dir = project_dir / "legacy_game"
    src_dir.mkdir()

    init_file = src_dir / "__init__.py"
    init_file.write_text('"""Legacy Game Island Package."""\n')

    yield project_dir
