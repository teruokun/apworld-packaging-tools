# SPDX-License-Identifier: MIT
"""CLI configuration loading from pyproject.toml."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class ConfigError(Exception):
    """Raised when configuration loading fails."""

    pass


@dataclass
class CLIConfig:
    """CLI configuration loaded from pyproject.toml.

    Attributes:
        project_dir: Directory containing pyproject.toml
        name: Package name
        version: Package version
        game_name: Display name of the game
        description: Package description
        authors: List of author names
        license: License identifier
        homepage: Homepage URL
        repository: Repository URL
        keywords: List of keywords
        dependencies: List of pip requirement strings
        minimum_ap_version: Minimum compatible Archipelago version
        maximum_ap_version: Maximum compatible Archipelago version
        platforms: List of supported platforms
        vendor_exclude: Packages to exclude from vendoring
        source_dir: Source directory for the package
    """

    project_dir: Path
    name: str = ""
    version: str = ""
    game_name: str = ""
    description: str = ""
    authors: list[str] = field(default_factory=list)
    license: str = ""
    homepage: str = ""
    repository: str = ""
    keywords: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    minimum_ap_version: str = ""
    maximum_ap_version: str = ""
    platforms: list[str] = field(default_factory=list)
    vendor_exclude: list[str] = field(default_factory=list)
    source_dir: Optional[Path] = None

    @classmethod
    def from_pyproject(cls, project_dir: str | Path) -> "CLIConfig":
        """Load configuration from pyproject.toml.

        Args:
            project_dir: Directory containing pyproject.toml

        Returns:
            CLIConfig instance

        Raises:
            ConfigError: If the file is invalid or missing required fields
            FileNotFoundError: If pyproject.toml doesn't exist
        """
        project_path = Path(project_dir)
        pyproject_path = project_path / "pyproject.toml"

        if not pyproject_path.exists():
            raise FileNotFoundError(f"pyproject.toml not found in {project_path}")

        try:
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Invalid TOML syntax: {e}") from e

        return cls.from_pyproject_dict(pyproject, project_path)

    @classmethod
    def from_pyproject_dict(
        cls,
        pyproject: dict[str, Any],
        project_dir: Path,
    ) -> "CLIConfig":
        """Create CLIConfig from a parsed pyproject.toml dictionary.

        Args:
            pyproject: Parsed pyproject.toml as a dictionary
            project_dir: Directory containing pyproject.toml

        Returns:
            CLIConfig instance
        """
        project = pyproject.get("project", {})
        tool_island = pyproject.get("tool", {}).get("island", {})
        tool_island_vendor = tool_island.get("vendor", {})

        # Extract name
        name = project.get("name", "")

        # Extract version
        version = project.get("version", "")

        # Game name: from tool.island.game or derived from name
        game_name = tool_island.get("game", "")
        if not game_name and name:
            game_name = name.replace("-", " ").replace("_", " ").title()

        # Extract authors
        authors: list[str] = []
        for author in project.get("authors", []):
            if isinstance(author, dict):
                author_name = author.get("name", "")
                if author_name:
                    authors.append(author_name)
            elif isinstance(author, str):
                authors.append(author)

        # Extract URLs
        urls = project.get("urls", {})
        homepage = urls.get("Homepage") or urls.get("homepage") or ""
        repository = (
            urls.get("Repository")
            or urls.get("repository")
            or urls.get("Source")
            or urls.get("source")
            or ""
        )

        # Extract license
        license_field = project.get("license")
        license_text = ""
        if isinstance(license_field, str):
            license_text = license_field
        elif isinstance(license_field, dict):
            license_text = license_field.get("text", "") or license_field.get("file", "")

        # Extract dependencies
        dependencies = project.get("dependencies", [])

        # Vendor config
        vendor_exclude = tool_island_vendor.get("exclude", [])

        # Determine source directory
        source_dir = None
        src_path = project_dir / "src" / name.replace("-", "_") if name else None
        if src_path and src_path.exists():
            source_dir = src_path
        elif name:
            # Try direct package directory
            pkg_path = project_dir / name.replace("-", "_")
            if pkg_path.exists():
                source_dir = pkg_path

        return cls(
            project_dir=project_dir,
            name=name,
            version=version,
            game_name=game_name,
            description=project.get("description", ""),
            authors=authors,
            license=license_text,
            homepage=homepage,
            repository=repository,
            keywords=project.get("keywords", []),
            dependencies=dependencies,
            minimum_ap_version=tool_island.get("minimum_ap_version", ""),
            maximum_ap_version=tool_island.get("maximum_ap_version", ""),
            platforms=tool_island.get("platforms", []),
            vendor_exclude=vendor_exclude,
            source_dir=source_dir,
        )

    def has_pyproject(self) -> bool:
        """Check if pyproject.toml exists in the project directory."""
        return (self.project_dir / "pyproject.toml").exists()

    def has_manifest(self) -> bool:
        """Check if archipelago.json exists in the project directory."""
        return (self.project_dir / "archipelago.json").exists()


def find_project_root(start_dir: Optional[str | Path] = None) -> Path:
    """Find the project root by looking for pyproject.toml or archipelago.json.

    Args:
        start_dir: Directory to start searching from (defaults to cwd)

    Returns:
        Path to the project root directory

    Raises:
        ConfigError: If no project root is found
    """
    current = Path(start_dir) if start_dir else Path.cwd()
    current = current.resolve()

    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        if (current / "archipelago.json").exists():
            return current
        current = current.parent

    raise ConfigError("Could not find project root (no pyproject.toml or archipelago.json found)")


def load_config(project_dir: Optional[str | Path] = None) -> CLIConfig:
    """Load CLI configuration from the project directory.

    Args:
        project_dir: Project directory (defaults to finding project root)

    Returns:
        CLIConfig instance

    Raises:
        ConfigError: If configuration cannot be loaded
        FileNotFoundError: If project files don't exist
    """
    if project_dir is None:
        project_dir = find_project_root()

    project_path = Path(project_dir)

    if (project_path / "pyproject.toml").exists():
        return CLIConfig.from_pyproject(project_path)

    # Return minimal config for legacy mode
    return CLIConfig(project_dir=project_path)
