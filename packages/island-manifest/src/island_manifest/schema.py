# SPDX-License-Identifier: MIT
"""JSON Schema definition for Island manifest (island.json).

This module defines the schema for the runtime manifest embedded in .island files.
The schema extends the existing Island format while maintaining backward compatibility.
"""

from __future__ import annotations

# Semantic versioning regex pattern (same as island-version)
SEMVER_PATTERN = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# Supported platform values
PLATFORMS = ["windows", "macos", "linux"]

# Current Island schema version
CURRENT_SCHEMA_VERSION = 7
MIN_COMPATIBLE_VERSION = 5

# JSON Schema for island.json manifest
MANIFEST_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://archipelago.gg/schemas/island-manifest-v2.json",
    "title": "Island Manifest",
    "description": "Runtime manifest for Island packages (island.json)",
    "type": "object",
    "required": ["game", "version", "compatible_version", "entry_points"],
    "properties": {
        # Required fields (existing Island format)
        "game": {
            "type": "string",
            "description": "Display name of the game",
            "minLength": 1,
            "maxLength": 100,
        },
        "version": {
            "type": "integer",
            "description": "Island schema version",
            "const": CURRENT_SCHEMA_VERSION,
        },
        "compatible_version": {
            "type": "integer",
            "description": "Minimum Island schema version for compatibility",
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
            "description": "Short description of the Island package",
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
        "entry_points": {
            "type": "object",
            "description": "Entry points by type (e.g., ap-island)",
            "properties": {
                "ap-island": {
                    "type": "object",
                    "description": "WebWorld entry points for Archipelago",
                    "minProperties": 1,
                    "additionalProperties": {
                        "type": "string",
                        "pattern": r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*:[a-zA-Z_][a-zA-Z0-9_]*$",
                    },
                },
            },
            "required": ["ap-island"],
            "additionalProperties": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        },
        # Reserved for future external dependency specification
        # External dependencies are resources required for generation that cannot
        # be redistributed (e.g., game binaries for patch generation).
        # This field is currently ignored but reserved for future use when the
        # community reaches consensus on how to specify external resource requirements.
        "external_dependencies": {
            "type": ["array", "null"],
            "description": "Reserved for future external dependency specification. "
            "External dependencies are resources required for generation that cannot "
            "be redistributed (e.g., game binaries). Currently ignored.",
            "items": {
                "type": "object",
                "description": "External dependency specification (format TBD)",
            },
            "default": None,
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
    "external_dependencies": None,
}


def get_manifest_schema() -> dict:
    """Return a copy of the manifest JSON schema.

    Returns:
        A dictionary containing the JSON Schema for island.json
    """
    return MANIFEST_SCHEMA.copy()


def get_default_values() -> dict:
    """Return default values for optional manifest fields.

    Returns:
        A dictionary mapping field names to their default values
    """
    return MANIFEST_DEFAULTS.copy()
