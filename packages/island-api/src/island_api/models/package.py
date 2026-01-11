# SPDX-License-Identifier: MIT
"""Pydantic models for package data."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuthorModel(BaseModel):
    """Author information."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str | None = None


class EntryPointModel(BaseModel):
    """Entry point information."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    entry_point_type: str
    module: str
    attr: str


class DownloadStats(BaseModel):
    """Download statistics for a package."""

    total: int = Field(description="Total downloads across all versions")
    recent: int = Field(description="Downloads in the last 30 days")


class DistributionModel(BaseModel):
    """Distribution file information with external URL.

    In the registry-only model, distributions are hosted externally
    (e.g., GitHub Releases) and the registry stores only metadata and URLs.
    """

    model_config = ConfigDict(from_attributes=True)

    filename: str
    sha256: str
    size: int
    platform_tag: str
    external_url: str  # URL to download from (external host, not registry)
    registered_at: datetime | None = None
    url_status: str = "active"  # "active" or "unavailable"


class VersionListItem(BaseModel):
    """Brief version information for listing."""

    model_config = ConfigDict(from_attributes=True)

    version: str
    published_at: datetime
    yanked: bool = False
    pure_python: bool = True


class VersionMetadata(BaseModel):
    """Full version metadata."""

    model_config = ConfigDict(from_attributes=True)

    version: str
    game: str
    minimum_ap_version: str | None = None
    maximum_ap_version: str | None = None
    pure_python: bool = True
    published_at: datetime
    yanked: bool = False
    yank_reason: str | None = None
    distributions: list[DistributionModel] = Field(default_factory=list)


class PackageListItem(BaseModel):
    """Brief package information for listing."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    display_name: str
    description: str | None = None
    latest_version: str | None = None
    downloads: DownloadStats | None = None
    entry_points: list[EntryPointModel] = Field(default_factory=list)


class PackageMetadata(BaseModel):
    """Full package metadata."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    display_name: str
    description: str | None = None
    license: str | None = None
    homepage: str | None = None
    repository: str | None = None
    created_at: datetime
    updated_at: datetime
    authors: list[AuthorModel] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    latest_version: str | None = None
    versions: list[VersionListItem] = Field(default_factory=list)
    downloads: DownloadStats | None = None
