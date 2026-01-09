# SPDX-License-Identifier: MIT
"""Package download endpoints."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_session
from ..db.models import Distribution, Package, Version
from ..middleware.errors import PackageNotFoundError, VersionNotFoundError

router = APIRouter()


class DistributionNotFoundError(Exception):
    """Distribution file not found."""

    def __init__(self, package_name: str, version: str, filename: str):
        self.package_name = package_name
        self.version = version
        self.filename = filename
        super().__init__(f"Distribution '{filename}' not found for {package_name} {version}")


@router.get("/packages/{name}/{version}/download/{filename}")
async def download_distribution(
    name: str,
    version: str,
    filename: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Download a distribution file.

    Returns the file with SHA256 checksum in X-Checksum-SHA256 header.
    Also includes Content-Disposition header for proper filename handling.

    The download count is incremented for each successful download.
    """
    # Find the version and distribution
    query = (
        select(Version)
        .options(selectinload(Version.distributions))
        .where(Version.package_name == name)
        .where(Version.version == version)
    )
    result = await session.execute(query)
    ver = result.scalar_one_or_none()

    if ver is None:
        # Check if package exists for better error message
        pkg_query = select(Package).where(Package.name == name)
        pkg_result = await session.execute(pkg_query)
        if pkg_result.scalar_one_or_none() is None:
            raise PackageNotFoundError(name)
        raise VersionNotFoundError(name, version)

    # Find the distribution
    distribution = None
    for dist in ver.distributions:
        if dist.filename == filename:
            distribution = dist
            break

    if distribution is None:
        raise VersionNotFoundError(name, version)

    # Get storage config from app state
    config = request.app.state.config

    # Resolve file path based on storage backend
    if config.storage.backend == "local":
        file_path = Path(config.storage.local_path) / distribution.storage_path
        if not file_path.exists():
            raise VersionNotFoundError(name, version)

        # Increment download counts
        await _increment_download_count(session, distribution.id, name)

        # Return file with checksum header
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream",
            headers={
                "X-Checksum-SHA256": distribution.sha256,
                "Content-Length": str(distribution.size),
            },
        )
    elif config.storage.backend == "s3":
        # For S3, we would generate a presigned URL or proxy the request
        # For now, return a redirect to the S3 URL
        # This is a placeholder - actual S3 implementation would use boto3
        s3_url = f"https://{config.storage.s3_bucket}.s3.amazonaws.com/{config.storage.s3_prefix}{distribution.storage_path}"

        # Increment download counts
        await _increment_download_count(session, distribution.id, name)

        return Response(
            status_code=302,
            headers={
                "Location": s3_url,
                "X-Checksum-SHA256": distribution.sha256,
            },
        )
    else:
        raise ValueError(f"Unknown storage backend: {config.storage.backend}")


async def _increment_download_count(
    session: AsyncSession,
    distribution_id: int,
    package_name: str,
) -> None:
    """Increment download counts for distribution and package."""
    # Increment distribution download count
    await session.execute(
        update(Distribution)
        .where(Distribution.id == distribution_id)
        .values(download_count=Distribution.download_count + 1)
    )

    # Increment package total downloads
    await session.execute(
        update(Package)
        .where(Package.name == package_name)
        .values(total_downloads=Package.total_downloads + 1)
    )

    await session.commit()
