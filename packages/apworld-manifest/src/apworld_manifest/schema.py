# SPDX-License-Identifier: MIT
"""JSON Schema definition for APWorld manifest (archipelago.json).

This module defines the schema for the runtime manifest embedded in .apworld files.
The schema extends the existing APWorld format while maintaining backward compatibility.
"""

from __future__ import annotations

# Semantic versioning regex pattern (same as apworld-version)
SEMVER_PATTERN = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# Supported platform values
PLATFORMS = ["windows", "macos", "linux"]

# Current APContainer schema version
CURRENT_SCHEMA_VERSION = 7
MIN_COMPATIBLE_VERSION = 5

# JSON Schema for archipelago.json manifest
MANIFEST_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://archipelago.gg/schemas/apworld-manifest-v2.json",
    "title": "APWorld Manifest",
    "description": "Runtime manifest for APWorld packages (archipelago.json)",
    "type": "object",
    "required": ["game", "version", "compatible_version"],
    "properties": {
        # Required fields (existing APWorld format)
        "game": {
            "type": "string",
            "description": "Display name of the game",
            "minLength": 1,
            "maxLength": 100,
        },
        "version": {
            "type": "integer",
            "description": "APContainer schema version",
            "const": CURRENT_SCHEMA_VERSION,
        },
        "compatible_version": {
            "type": "integer",
            "description": "Minimum APContainer schema version for compatibility",
            "minimum": MIN_COMPATIBLE_VERSION,
            "maximum": CURRENT_SCHEMA_VERSION,
        },
        # Extended fields (new in v2 schema)
        "world_version": {
            "type": "string",
            "description": "Package version following semantic versioning",
            "pattern": SEMVER_PATTERN,
        },
        "minimum_ap_version": {
            "type": "string",
            "description": "Minimum compatible Archipelago core version",
            "pattern": SEMVER_PATTERN,
        },
        "maximum_ap_version": {
            "type": "string",
            "description": "Maximum compatible Archipelago core version",
            "pattern": SEMVER_PATTERN,
        },
        "authors": {
            "type": "array",
            "description": "List of package authors",
            "items": {"type": "string", "minLength": 1},
            "default": [],
        },
        "description": {
            "type": "string",
            "description": "Short description of the APWorld",
            "maxLength": 500,
            "default": "",
        },
        "license": {
            "type": "string",
            "description": "SPDX license identifier",
            "default": "",
        },
        "homepage": {
            "type": "string",
            "description": "URL to the project homepage",
            "format": "uri",
        },
        "repository": {
            "type": "string",
            "description": "URL to the source repository",
            "format": "uri",
        },
        "keywords": {
            "type": "array",
            "description": "Keywords for package discovery",
            "items": {"type": "string", "minLength": 1, "maxLength": 50},
            "default": [],
        },
        "vendored_dependencies": {
            "type": "object",
            "description": "Map of vendored package names to versions",
            "additionalProperties": {"type": "string"},
            "default": {},
        },
        "platforms": {
            "type": "array",
            "description": "Supported operating systems",
            "items": {"type": "string", "enum": PLATFORMS},
            "default": ["windows", "macos", "linux"],
        },
        "pure_python": {
            "type": "boolean",
            "description": "Whether the package is pure Python (no native extensions)",
            "default": True,
        },
    },
    "additionalProperties": True,  # Allow unknown fields for forward compatibility
}

# Default values for optional fields
MANIFEST_DEFAULTS: dict = {
    "authors": [],
    "description": "",
    "license": "",
    "keywords": [],
    "vendored_dependencies": {},
    "platforms": ["windows", "macos", "linux"],
    "pure_python": True,
}


def get_manifest_schema() -> dict:
    """Return a copy of the manifest JSON schema.

    Returns:
        A dictionary containing the JSON Schema for archipelago.json
    """
    return MANIFEST_SCHEMA.copy()


def get_default_values() -> dict:
    """Return default values for optional manifest fields.

    Returns:
        A dictionary mapping field names to their default values
    """
    return MANIFEST_DEFAULTS.copy()
