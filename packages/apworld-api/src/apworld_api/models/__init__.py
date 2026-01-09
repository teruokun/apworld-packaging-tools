# SPDX-License-Identifier: MIT
"""Pydantic models for API requests and responses."""

from .package import (
    AuthorModel,
    DistributionModel,
    DownloadStats,
    PackageListItem,
    PackageMetadata,
    VersionListItem,
    VersionMetadata,
)
from .responses import (
    ErrorDetail,
    ErrorResponse,
    IndexResponse,
    PackageListResponse,
    SearchResponse,
    VersionListResponse,
)

__all__ = [
    # Package models
    "AuthorModel",
    "DistributionModel",
    "DownloadStats",
    "PackageListItem",
    "PackageMetadata",
    "VersionListItem",
    "VersionMetadata",
    # Response models
    "ErrorDetail",
    "ErrorResponse",
    "IndexResponse",
    "PackageListResponse",
    "SearchResponse",
    "VersionListResponse",
]
