# SPDX-License-Identifier: MIT
"""Manifest validation for APWorld packages.

This module provides validation of archipelago.json manifests against the schema,
with structured error reporting and default value application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator, ValidationError

from .schema import MANIFEST_DEFAULTS, MANIFEST_SCHEMA


class ManifestError(Exception):
    """Base exception for manifest-related errors."""

    pass


class ManifestValidationError(ManifestError):
    """Raised when manifest validation fails.

    Attributes:
        errors: List of validation errors with field paths and messages
    """

    def __init__(self, errors: list[ValidationErrorDetail]):
        self.errors = errors
        message = f"Manifest validation failed with {len(errors)} error(s)"
        if errors:
            message += f": {errors[0].message}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ValidationErrorDetail:
    """Details about a single validation error.

    Attributes:
        field: JSON path to the invalid field (e.g., "world_version" or "authors[0]")
        message: Human-readable error message
        value: The invalid value that caused the error (if available)
    """

    field: str
    message: str
    value: Any = None


@dataclass
class ValidationResult:
    """Result of manifest validation.

    Attributes:
        valid: Whether the manifest is valid
        errors: List of validation errors (empty if valid)
        manifest: The validated manifest with defaults applied (None if invalid)
    """

    valid: bool
    errors: list[ValidationErrorDetail] = field(default_factory=list)
    manifest: dict | None = None


def _json_path_from_error(error: ValidationError) -> str:
    """Convert a jsonschema error path to a readable field path."""
    if not error.absolute_path:
        return "<root>"
    parts = []
    for part in error.absolute_path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            if parts:
                parts.append(f".{part}")
            else:
                parts.append(str(part))
    return "".join(parts)


def _format_error_message(error: ValidationError) -> str:
    """Format a jsonschema error into a human-readable message."""
    if error.validator == "required":
        missing = error.validator_value
        if isinstance(missing, list) and len(missing) == 1:
            return f"Missing required field: {missing[0]}"
        return f"Missing required fields: {', '.join(missing)}"

    if error.validator == "type":
        expected = error.validator_value
        actual = type(error.instance).__name__
        return f"Expected {expected}, got {actual}"

    if error.validator == "pattern":
        return f"Value does not match required pattern"

    if error.validator == "enum":
        allowed = ", ".join(repr(v) for v in error.validator_value)
        return f"Value must be one of: {allowed}"

    if error.validator == "minLength":
        return f"String must be at least {error.validator_value} character(s)"

    if error.validator == "maxLength":
        return f"String must be at most {error.validator_value} character(s)"

    if error.validator == "minimum":
        return f"Value must be at least {error.validator_value}"

    if error.validator == "maximum":
        return f"Value must be at most {error.validator_value}"

    if error.validator == "const":
        return f"Value must be {error.validator_value}"

    if error.validator == "format":
        return f"Invalid {error.validator_value} format"

    return error.message


def validate_manifest(manifest: dict) -> ValidationResult:
    """Validate an archipelago.json manifest against the schema.

    This function validates the manifest structure and values, then applies
    default values for any missing optional fields.

    Args:
        manifest: A dictionary containing the manifest data

    Returns:
        ValidationResult with validation status, errors, and processed manifest

    Example:
        >>> result = validate_manifest({"game": "Test", "version": 7, "compatible_version": 7})
        >>> result.valid
        True
        >>> result.manifest["pure_python"]
        True
    """
    if not isinstance(manifest, dict):
        return ValidationResult(
            valid=False,
            errors=[
                ValidationErrorDetail(
                    field="<root>",
                    message=f"Manifest must be a dictionary, got {type(manifest).__name__}",
                    value=manifest,
                )
            ],
        )

    validator = Draft202012Validator(MANIFEST_SCHEMA)
    errors: list[ValidationErrorDetail] = []

    for error in validator.iter_errors(manifest):
        errors.append(
            ValidationErrorDetail(
                field=_json_path_from_error(error),
                message=_format_error_message(error),
                value=error.instance if error.absolute_path else None,
            )
        )

    if errors:
        return ValidationResult(valid=False, errors=errors)

    # Apply defaults for missing optional fields
    result_manifest = manifest.copy()
    for key, default_value in MANIFEST_DEFAULTS.items():
        if key not in result_manifest:
            if isinstance(default_value, (list, dict)):
                result_manifest[key] = default_value.copy()
            else:
                result_manifest[key] = default_value

    return ValidationResult(valid=True, manifest=result_manifest)


def validate_manifest_strict(manifest: dict) -> dict:
    """Validate a manifest and raise an exception if invalid.

    This is a convenience function that raises ManifestValidationError
    if validation fails, otherwise returns the validated manifest with defaults.

    Args:
        manifest: A dictionary containing the manifest data

    Returns:
        The validated manifest with default values applied

    Raises:
        ManifestValidationError: If the manifest is invalid
    """
    result = validate_manifest(manifest)
    if not result.valid:
        raise ManifestValidationError(result.errors)
    return result.manifest  # type: ignore[return-value]
