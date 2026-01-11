# SPDX-License-Identifier: MIT
"""Build configuration for Island packages.

This module provides the BuildConfig dataclass that holds all configuration
needed to build Island distributions.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .filename import normalize_name


class BuildConfigError(Exception):
    """Raised when build configuration is invalid."""

    pass


# Default schema version for island.json
DEFAULT_SCHEMA_VERSION = 7
MIN_COMPATIBLE_VERSION = 5

# Default include patterns for source files
DEFAULT_INCLUDE_PATTERNS = [
    "*.py",
    "**/*.py",
    "*.json",
    "**/*.json",
    "*.yaml",
    "**/*.yaml",
    "*.yml",
    "**/*.yml",
    "*.txt",
    "**/*.txt",
    "*.md",
    "**/*.md",
]

# Default exclude patterns
DEFAULT_EXCLUDE_PATTERNS = [
    "__pycache__",
    "__pycache__/*",
    "*.pyc",
    "*.pyo",
    ".git",
    ".git/*",
    ".gitignore",
    ".hg",
    ".hg/*",
    ".svn",
    ".svn/*",
    ".tox",
    ".tox/*",
    ".nox",
    ".nox/*",
    ".pytest_cache",
    ".pytest_cache/*",
    ".mypy_cache",
    ".mypy_cache/*",
    ".ruff_cache",
    ".ruff_cache/*",
    "*.egg-info",
    "*.egg-info/*",
    "dist",
    "dist/*",
    "build",
    "build/*",
    ".eggs",
    ".eggs/*",
    "tests",
    "tests/*",
    "test",
    "test/*",
    "test_*.py",
    "*_test.py",
    ".DS_Store",
    "Thumbs.db",
    "*.swp",
    "*.swo",
    "*~",
]


@dataclass
class BuildConfig:
    """Configuration for building Island distributions.

    Attributes:
        name: Package name (from pyproject.toml [project].name)
        version: Package version (semver)
        game_name: Display name of the game
        source_dir: Root directory containing source files
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
        schema_version: APContainer schema version
        compatible_version: Minimum compatible schema version
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        vendor_exclude: Packages to exclude from vendoring
    """

    name: str
    version: str
    game_name: str
    source_dir: Path

    # Optional metadata
    description: str = ""
    authors: list[str] = field(default_factory=list)
    license: str = ""
    homepage: str = ""
    repository: str = ""
    keywords: list[str] = field(default_factory=list)

    # Dependencies
    dependencies: list[str] = field(default_factory=list)

    # AP compatibility
    minimum_ap_version: str = ""
    maximum_ap_version: str = ""
    platforms: list[str] = field(default_factory=list)

    # Schema versions
    schema_version: int = DEFAULT_SCHEMA_VERSION
    compatible_version: int = MIN_COMPATIBLE_VERSION

    # Build patterns
    include_patterns: list[str] = field(default_factory=lambda: DEFAULT_INCLUDE_PATTERNS.copy())
    exclude_patterns: list[str] = field(default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy())

    # Vendoring config
    vendor_exclude: list[str] = field(default_factory=list)

    @property
    def normalized_name(self) -> str:
        """Return the normalized package name for filenames."""
        return normalize_name(self.name)

    @classmethod
    def from_pyproject(
        cls,
        pyproject_path: str | Path,
        source_dir: Optional[str | Path] = None,
    ) -> "BuildConfig":
        """Create a BuildConfig from a pyproject.toml file.

        Args:
            pyproject_path: Path to pyproject.toml
            source_dir: Source directory (defaults to directory containing pyproject.toml)

        Returns:
            BuildConfig instance

        Raises:
            BuildConfigError: If the file is invalid or missing required fields
            FileNotFoundError: If the file doesn't exist
        """
        path = Path(pyproject_path)
        if not path.exists():
            raise FileNotFoundError(f"pyproject.toml not found: {path}")

        try:
            with open(path, "rb") as f:
                pyproject = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise BuildConfigError(f"Invalid TOML syntax: {e}") from e

        return cls.from_pyproject_dict(
            pyproject,
            source_dir=source_dir or path.parent,
        )

    @classmethod
    def from_pyproject_dict(
        cls,
        pyproject: dict[str, Any],
        source_dir: str | Path,
    ) -> "BuildConfig":
        """Create a BuildConfig from a parsed pyproject.toml dictionary.

        Args:
            pyproject: Parsed pyproject.toml as a dictionary
            source_dir: Source directory

        Returns:
            BuildConfig instance

        Raises:
            BuildConfigError: If required fields are missing
        """
        project = pyproject.get("project", {})
        tool_island = pyproject.get("tool", {}).get("island", {})
        tool_island_build = tool_island.get("build", {})
        tool_island_vendor = tool_island.get("vendor", {})

        # Required: name
        name = project.get("name")
        if not name:
            raise BuildConfigError("Missing required field: [project].name")

        # Required: version
        version = project.get("version")
        if not version:
            raise BuildConfigError("Missing required field: [project].version")

        # Game name: from tool.island.game or derived from name
        game_name = tool_island.get("game")
        if not game_name:
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

        # Build patterns
        include_patterns = tool_island_build.get("include", DEFAULT_INCLUDE_PATTERNS.copy())
        exclude_patterns = tool_island_build.get("exclude", DEFAULT_EXCLUDE_PATTERNS.copy())

        # Vendor config
        vendor_exclude = tool_island_vendor.get("exclude", [])

        return cls(
            name=name,
            version=version,
            game_name=game_name,
            source_dir=Path(source_dir),
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
            schema_version=tool_island.get("schema_version", DEFAULT_SCHEMA_VERSION),
            compatible_version=tool_island.get("compatible_version", MIN_COMPATIBLE_VERSION),
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            vendor_exclude=vendor_exclude,
        )

    @classmethod
    def from_manifest(
        cls,
        manifest_path: str | Path,
        source_dir: str | Path,
    ) -> "BuildConfig":
        """Create a BuildConfig from an island.json manifest (legacy mode).

        Args:
            manifest_path: Path to island.json
            source_dir: Source directory

        Returns:
            BuildConfig instance

        Raises:
            BuildConfigError: If the manifest is invalid
            FileNotFoundError: If the file doesn't exist
        """
        import json

        path = Path(manifest_path)
        if not path.exists():
            raise FileNotFoundError(f"island.json not found: {path}")

        try:
            with open(path) as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise BuildConfigError(f"Invalid JSON syntax: {e}") from e

        # Required: game
        game_name = manifest.get("game")
        if not game_name:
            raise BuildConfigError("Missing required field: game")

        # Derive name from game name
        name = game_name.lower().replace(" ", "-").replace("_", "-")

        # Version
        version = manifest.get("world_version", "0.0.0")

        return cls(
            name=name,
            version=version,
            game_name=game_name,
            source_dir=Path(source_dir),
            description=manifest.get("description", ""),
            authors=manifest.get("authors", []),
            license=manifest.get("license", ""),
            homepage=manifest.get("homepage", ""),
            repository=manifest.get("repository", ""),
            keywords=manifest.get("keywords", []),
            minimum_ap_version=manifest.get("minimum_ap_version", ""),
            maximum_ap_version=manifest.get("maximum_ap_version", ""),
            platforms=manifest.get("platforms", []),
            schema_version=manifest.get("version", DEFAULT_SCHEMA_VERSION),
            compatible_version=manifest.get("compatible_version", MIN_COMPATIBLE_VERSION),
        )

    def to_manifest(self) -> dict[str, Any]:
        """Convert the config to an island.json manifest dictionary.

        Returns:
            Manifest dictionary
        """
        manifest: dict[str, Any] = {
            "game": self.game_name,
            "version": self.schema_version,
            "compatible_version": self.compatible_version,
        }

        if self.version:
            manifest["world_version"] = self.version

        if self.minimum_ap_version:
            manifest["minimum_ap_version"] = self.minimum_ap_version

        if self.maximum_ap_version:
            manifest["maximum_ap_version"] = self.maximum_ap_version

        if self.authors:
            manifest["authors"] = self.authors

        if self.description:
            manifest["description"] = self.description

        if self.license:
            manifest["license"] = self.license

        if self.homepage:
            manifest["homepage"] = self.homepage

        if self.repository:
            manifest["repository"] = self.repository

        if self.keywords:
            manifest["keywords"] = self.keywords

        if self.platforms:
            manifest["platforms"] = self.platforms

        # Default to pure Python
        manifest["pure_python"] = True

        return manifest
