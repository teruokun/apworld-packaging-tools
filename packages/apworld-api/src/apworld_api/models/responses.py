# SPDX-License-Identifier: MIT
"""Pydantic models for API response wrappers."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .package import PackageListItem, VersionListItem


class ErrorDetail(BaseModel):
    """Detailed error information for a specific field."""

    field: str
    error: str


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: dict = Field(description="Error object containing code, message, and optional details")

    @classmethod
    def create(
        cls, code: str, message: str, details: list[ErrorDetail] | None = None
    ) -> "ErrorResponse":
        """Create an error response."""
        error_obj: dict[str, Any] = {"code": code, "message": message}
        if details:
            error_obj["details"] = [d.model_dump() for d in details]
        return cls(error=error_obj)


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=100, description="Items per page")
    total: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")


class PackageListResponse(BaseModel):
    """Response for package listing endpoint."""

    packages: list[PackageListItem]
    pagination: PaginationInfo


class VersionListResponse(BaseModel):
    """Response for version listing endpoint."""

    package_name: str
    versions: list[VersionListItem]
    total: int


class SearchResponse(BaseModel):
    """Response for search endpoint."""

    results: list[PackageListItem]
    query: str
    filters: dict[str, str | None] = Field(default_factory=dict)
    total: int


class IndexPackageEntry(BaseModel):
    """Package entry in the JSON index."""

    display_name: str
    description: str | None = None
    latest_version: str | None = None
    versions: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Map of version string to version metadata",
    )


class IndexResponse(BaseModel):
    """Full package index for offline tooling."""

    packages: dict[str, IndexPackageEntry] = Field(
        description="Map of package name to package data"
    )
    generated_at: datetime
    total_packages: int
    total_versions: int
