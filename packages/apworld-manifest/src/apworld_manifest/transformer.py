# SPDX-License-Identifier: MIT
"""Transform pyproject.toml to archipelago.json manifest.

This module parses PEP 621 project metadata and APWorld-specific configuration
from pyproject.toml and generates the runtime archipelago.json manifest.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .schema import CURRENT_SCHEMA_VERSION, MANIFEST_DEFAULTS, MIN_COMPATIBLE_VERSION
from .validator import ManifestError


class ManifestTransformError(ManifestError):
    """Raised when transformation from pyproject.toml fails."""

    pass


@dataclass
class TransformConfig:
    """Configuration for pyproject.toml transformation.

    Attributes:
        schema_version: APContainer schema version to use
        compatible_version: Minimum compatible schema version
    """

    schema_version: int = CURRENT_SCHEMA_VERSION
    compatible_version: int = MIN_COMPATIBLE_VERSION


def _extract_authors(project: dict) -> list[str]:
    """Extract author names from PEP 621 authors field."""
    authors = project.get("authors", [])
    result = []
    for author in authors:
        if isinstance(author, dict):
            name = author.get("name", "")
            if name:
                result.append(name)
        elif isinstance(author, str):
            result.append(author)
    return result


def _extract_urls(project: dict) -> tuple[str | None, str | None]:
    """Extract homepage and repository URLs from project.urls."""
    urls = project.get("urls", {})
    homepage = urls.get("Homepage") or urls.get("homepage")
    repository = (
        urls.get("Repository") or urls.get("repository") or urls.get("Source") or urls.get("source")
    )
    return homepage, repository


def _extract_license(project: dict) -> str:
    """Extract license from PEP 621 license field."""
    license_field = project.get("license")
    if license_field is None:
        return ""
    if isinstance(license_field, str):
        return license_field
    if isinstance(license_field, dict):
        return license_field.get("text", "") or license_field.get("file", "")
    return ""


def transform_pyproject(
    pyproject_path: str | Path,
    config: TransformConfig | None = None,
) -> dict[str, Any]:
    """Transform a pyproject.toml file into an archipelago.json manifest.

    This function reads the [project] section (PEP 621) and [tool.apworld] section
    from pyproject.toml and generates a valid archipelago.json manifest.

    Args:
        pyproject_path: Path to the pyproject.toml file
        config: Optional transformation configuration

    Returns:
        A dictionary containing the archipelago.json manifest

    Raises:
        ManifestTransformError: If the file cannot be read or is missing required fields
        FileNotFoundError: If the pyproject.toml file does not exist

    Example:
        >>> manifest = transform_pyproject("path/to/pyproject.toml")
        >>> manifest["game"]
        'Pokemon Emerald'
    """
    config = config or TransformConfig()
    path = Path(pyproject_path)

    if not path.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {path}")

    try:
        with open(path, "rb") as f:
            pyproject = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ManifestTransformError(f"Invalid TOML syntax: {e}") from e

    project = pyproject.get("project", {})
    tool_apworld = pyproject.get("tool", {}).get("apworld", {})

    # Extract game name (required) - from tool.apworld or project.name
    game = tool_apworld.get("game")
    if not game:
        # Fall back to project name, converting to title case
        project_name = project.get("name", "")
        if project_name:
            game = project_name.replace("-", " ").replace("_", " ").title()
        else:
            raise ManifestTransformError(
                "Missing required field: 'game' in [tool.apworld] or 'name' in [project]"
            )

    # Build the manifest
    manifest: dict[str, Any] = {
        "game": game,
        "version": config.schema_version,
        "compatible_version": config.compatible_version,
    }

    # Add world_version from project.version
    version = project.get("version")
    if version:
        manifest["world_version"] = version

    # Add AP version compatibility from tool.apworld
    min_ap = tool_apworld.get("minimum_ap_version")
    if min_ap:
        manifest["minimum_ap_version"] = min_ap

    max_ap = tool_apworld.get("maximum_ap_version")
    if max_ap:
        manifest["maximum_ap_version"] = max_ap

    # Add authors
    authors = _extract_authors(project)
    if authors:
        manifest["authors"] = authors

    # Add description
    description = project.get("description", "")
    if description:
        manifest["description"] = description

    # Add license
    license_text = _extract_license(project)
    if license_text:
        manifest["license"] = license_text

    # Add URLs
    homepage, repository = _extract_urls(project)
    if homepage:
        manifest["homepage"] = homepage
    if repository:
        manifest["repository"] = repository

    # Add keywords
    keywords = project.get("keywords", [])
    if keywords:
        manifest["keywords"] = keywords

    # Add platform info from tool.apworld
    platforms = tool_apworld.get("platforms")
    if platforms:
        manifest["platforms"] = platforms

    # Add pure_python flag from tool.apworld
    pure_python = tool_apworld.get("pure_python")
    if pure_python is not None:
        manifest["pure_python"] = pure_python

    # Apply defaults for missing optional fields
    for key, default_value in MANIFEST_DEFAULTS.items():
        if key not in manifest:
            if isinstance(default_value, (list, dict)):
                manifest[key] = default_value.copy()
            else:
                manifest[key] = default_value

    return manifest


def transform_pyproject_dict(
    pyproject: dict[str, Any],
    config: TransformConfig | None = None,
) -> dict[str, Any]:
    """Transform a pyproject.toml dictionary into an archipelago.json manifest.

    This is a convenience function for when you already have the parsed TOML data.

    Args:
        pyproject: Parsed pyproject.toml as a dictionary
        config: Optional transformation configuration

    Returns:
        A dictionary containing the archipelago.json manifest

    Raises:
        ManifestTransformError: If required fields are missing
    """
    config = config or TransformConfig()

    project = pyproject.get("project", {})
    tool_apworld = pyproject.get("tool", {}).get("apworld", {})

    # Extract game name (required)
    game = tool_apworld.get("game")
    if not game:
        project_name = project.get("name", "")
        if project_name:
            game = project_name.replace("-", " ").replace("_", " ").title()
        else:
            raise ManifestTransformError(
                "Missing required field: 'game' in [tool.apworld] or 'name' in [project]"
            )

    manifest: dict[str, Any] = {
        "game": game,
        "version": config.schema_version,
        "compatible_version": config.compatible_version,
    }

    # Add world_version from project.version
    version = project.get("version")
    if version:
        manifest["world_version"] = version

    # Add AP version compatibility
    min_ap = tool_apworld.get("minimum_ap_version")
    if min_ap:
        manifest["minimum_ap_version"] = min_ap

    max_ap = tool_apworld.get("maximum_ap_version")
    if max_ap:
        manifest["maximum_ap_version"] = max_ap

    # Add authors
    authors = _extract_authors(project)
    if authors:
        manifest["authors"] = authors

    # Add description
    description = project.get("description", "")
    if description:
        manifest["description"] = description

    # Add license
    license_text = _extract_license(project)
    if license_text:
        manifest["license"] = license_text

    # Add URLs
    homepage, repository = _extract_urls(project)
    if homepage:
        manifest["homepage"] = homepage
    if repository:
        manifest["repository"] = repository

    # Add keywords
    keywords = project.get("keywords", [])
    if keywords:
        manifest["keywords"] = keywords

    # Add platform info
    platforms = tool_apworld.get("platforms")
    if platforms:
        manifest["platforms"] = platforms

    # Add pure_python flag
    pure_python = tool_apworld.get("pure_python")
    if pure_python is not None:
        manifest["pure_python"] = pure_python

    # Apply defaults
    for key, default_value in MANIFEST_DEFAULTS.items():
        if key not in manifest:
            if isinstance(default_value, (list, dict)):
                manifest[key] = default_value.copy()
            else:
                manifest[key] = default_value

    return manifest
