# SPDX-License-Identifier: MIT
"""Manifest schema, validation, and transformation for Island packages.

This package provides utilities for working with Island manifests:
- JSON Schema definition for island.json
- Validation with structured error reporting
- Transformation from pyproject.toml to island.json

Example:
    >>> from island_manifest import validate_manifest, transform_pyproject
    >>>
    >>> # Validate an existing manifest
    >>> result = validate_manifest({"game": "Test", "version": 7, "compatible_version": 7})
    >>> result.valid
    True
    >>>
    >>> # Transform from pyproject.toml
    >>> manifest = transform_pyproject("path/to/pyproject.toml")
"""

__version__ = "0.1.0"

from .schema import (
    CURRENT_SCHEMA_VERSION,
    MANIFEST_DEFAULTS,
    MANIFEST_SCHEMA,
    MIN_COMPATIBLE_VERSION,
    PLATFORMS,
    SEMVER_PATTERN,
    get_default_values,
    get_manifest_schema,
)
from .transformer import (
    ManifestTransformError,
    TransformConfig,
    transform_pyproject,
    transform_pyproject_dict,
)
from .validator import (
    ManifestError,
    ManifestValidationError,
    validate_manifest,
    validate_manifest_strict,
    ValidationErrorDetail,
    ValidationResult,
)

__all__ = [
    # Schema
    "MANIFEST_SCHEMA",
    "MANIFEST_DEFAULTS",
    "SEMVER_PATTERN",
    "PLATFORMS",
    "CURRENT_SCHEMA_VERSION",
    "MIN_COMPATIBLE_VERSION",
    "get_manifest_schema",
    "get_default_values",
    # Validation
    "validate_manifest",
    "validate_manifest_strict",
    "ValidationResult",
    "ValidationErrorDetail",
    "ManifestError",
    "ManifestValidationError",
    # Transformation
    "transform_pyproject",
    "transform_pyproject_dict",
    "TransformConfig",
    "ManifestTransformError",
]
