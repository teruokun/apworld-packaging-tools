# SPDX-License-Identifier: MIT
"""Pydantic models for package registration requests."""

import re

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def validate_sha256_format(value: str) -> str:
    """Validate SHA256 is exactly 64 lowercase hex characters.

    Args:
        value: The checksum string to validate

    Returns:
        The validated checksum string (lowercase)

    Raises:
        ValueError: If the checksum format is invalid
    """
    # Convert to lowercase for consistency
    value = value.lower()

    # Check length
    if len(value) != 64:
        raise ValueError(f"sha256 must be exactly 64 characters, got {len(value)}")

    # Check all characters are valid hex
    if not re.match(r"^[0-9a-f]{64}$", value):
        raise ValueError("sha256 must contain only lowercase hexadecimal characters (0-9, a-f)")

    return value


class DistributionRegistration(BaseModel):
    """Registration data for a single distribution file.

    Represents an externally-hosted distribution asset that will be
    registered with the registry. The registry will verify the URL
    is accessible and the checksum matches before accepting.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    filename: str = Field(
        ...,
        description="Filename of the distribution (e.g., my_game-1.0.0-py3-none-any.island)",
        min_length=1,
        max_length=255,
    )
    url: HttpUrl = Field(
        ...,
        description="HTTPS URL where the distribution can be downloaded",
    )
    sha256: str = Field(
        ...,
        description="SHA256 checksum of the file (64 lowercase hex characters)",
    )
    size: int = Field(
        ...,
        description="Size of the file in bytes",
        gt=0,
    )
    platform_tag: str = Field(
        ...,
        description="Platform compatibility tag (e.g., py3-none-any, cp311-win_amd64)",
        min_length=1,
        max_length=100,
    )

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        """Validate SHA256 is 64 lowercase hex characters."""
        return validate_sha256_format(v)

    @field_validator("url")
    @classmethod
    def validate_https_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate URL uses HTTPS scheme."""
        if v.scheme != "https":
            raise ValueError("URL must use HTTPS scheme")
        return v


class PackageRegistration(BaseModel):
    """Registration request for a package version.

    Contains all metadata and distribution information needed to
    register a new package version with the registry.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        description="Package name (lowercase, alphanumeric with hyphens/underscores)",
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    version: str = Field(
        ...,
        description="Package version (semantic versioning format)",
        min_length=1,
        max_length=50,
    )
    game: str = Field(
        ...,
        description="Name of the game this package supports",
        min_length=1,
        max_length=100,
    )
    description: str = Field(
        ...,
        description="Package description",
        min_length=1,
    )
    authors: list[str] = Field(
        ...,
        description="List of package authors",
        min_length=1,
    )
    minimum_ap_version: str = Field(
        ...,
        description="Minimum compatible Archipelago version",
    )
    maximum_ap_version: str | None = Field(
        default=None,
        description="Maximum compatible Archipelago version (optional)",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords for search and discovery",
    )
    homepage: str | None = Field(
        default=None,
        description="Package homepage URL",
    )
    repository: str | None = Field(
        default=None,
        description="Source code repository URL",
    )
    license: str | None = Field(
        default=None,
        description="Package license identifier",
    )
    entry_points: dict[str, str] = Field(
        ...,
        description="Entry points for ap-island discovery (name -> module:attr)",
        min_length=1,
    )
    distributions: list[DistributionRegistration] = Field(
        ...,
        description="List of distribution files to register",
        min_length=1,
    )

    # Provenance information
    source_repository: str | None = Field(
        default=None,
        description="Source repository URL for provenance tracking",
    )
    source_commit: str | None = Field(
        default=None,
        description="Git commit SHA for provenance tracking (40 hex characters)",
    )

    @field_validator("source_commit")
    @classmethod
    def validate_commit_sha(cls, v: str | None) -> str | None:
        """Validate commit SHA is 40 hex characters if provided."""
        if v is None:
            return v
        v = v.lower()
        if not re.match(r"^[0-9a-f]{40}$", v):
            raise ValueError("source_commit must be 40 lowercase hex characters")
        return v


class RegistrationResponse(BaseModel):
    """Response after successful package registration."""

    package_name: str = Field(
        ...,
        description="Name of the registered package",
    )
    version: str = Field(
        ...,
        description="Version that was registered",
    )
    registered_distributions: list[str] = Field(
        ...,
        description="List of distribution filenames that were registered",
    )
    registry_url: str = Field(
        ...,
        description="URL to view the registered package version",
    )
