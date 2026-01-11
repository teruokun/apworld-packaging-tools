# SPDX-License-Identifier: MIT
"""Package download endpoints.

In the registry model, the registry does NOT serve files directly.
Instead, it redirects to external URLs where files are hosted.
Clients are responsible for downloading from external URLs and
verifying checksums locally.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
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


def _get_platform_specificity(platform_tag: str) -> int:
    """Calculate specificity score for a platform tag.

    Higher scores indicate more specific platforms.
    py3-none-any is the least specific (universal).

    Args:
        platform_tag: Platform tag string (e.g., "py3-none-any", "cp311-cp311-win_amd64")

    Returns:
        Specificity score (0 = universal, higher = more specific)
    """
    parts = platform_tag.split("-")
    if len(parts) != 3:
        return 0

    python, abi, platform = parts
    score = 0

    # Python version specificity
    if python != "py3":
        score += 10  # Specific Python version (e.g., cp311)

    # ABI specificity
    if abi != "none":
        score += 5  # Specific ABI

    # Platform specificity
    if platform != "any":
        score += 20  # Specific platform

    return score


def _is_platform_compatible(dist_tag: str, requested_tag: str | None) -> bool:
    """Check if a distribution's platform tag is compatible with the requested platform.

    Args:
        dist_tag: Distribution's platform tag
        requested_tag: Requested platform tag (None means any)

    Returns:
        True if compatible
    """
    if requested_tag is None:
        return True

    # Universal packages are always compatible
    if dist_tag == "py3-none-any":
        return True

    # Exact match
    if dist_tag == requested_tag:
        return True

    # Parse tags for more nuanced matching
    dist_parts = dist_tag.split("-")
    req_parts = requested_tag.split("-")

    if len(dist_parts) != 3 or len(req_parts) != 3:
        return False

    dist_python, dist_abi, dist_platform = dist_parts
    req_python, req_abi, req_platform = req_parts

    # Check Python compatibility
    # py3 is compatible with any py3.x or cpython 3.x
    if dist_python == "py3":
        if not (req_python == "py3" or req_python.startswith("cp3")):
            return False
    elif dist_python != req_python:
        return False

    # Check ABI compatibility
    # none is compatible with any ABI
    if dist_abi != "none" and dist_abi != req_abi:
        return False

    # Check platform compatibility
    # any is compatible with any platform
    if dist_platform != "any" and dist_platform != req_platform:
        return False

    return True


def _select_best_distribution(
    distributions: list[Distribution], platform: str | None
) -> Distribution | None:
    """Select the most specific compatible distribution for the requested platform.

    Args:
        distributions: List of available distributions
        platform: Requested platform tag (None means prefer most specific available)

    Returns:
        Best matching distribution, or None if no compatible distribution found
    """
    compatible = []
    for dist in distributions:
        if _is_platform_compatible(dist.platform_tag, platform):
            compatible.append(dist)

    if not compatible:
        return None

    # Sort by specificity (descending) to get most specific first
    compatible.sort(key=lambda d: _get_platform_specificity(d.platform_tag), reverse=True)

    # If a specific platform was requested, prefer exact match
    if platform:
        for dist in compatible:
            if dist.platform_tag == platform:
                return dist

    # Return most specific compatible distribution
    return compatible[0]


@router.get("/packages/{name}/{version}/download/{filename}")
async def download_distribution(
    name: str,
    version: str,
    filename: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Redirect to external URL for distribution download.

    In the registry model, the registry does NOT serve files directly.
    Instead, it redirects to the external URL where the file is hosted.

    Returns a redirect with SHA256 checksum in X-Checksum-SHA256 header.
    Clients should verify the checksum after downloading from the external URL.
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

    # Check if URL is available
    if distribution.url_status != "active":
        raise VersionNotFoundError(name, version)

    # Redirect to external URL with checksum header for client verification
    return Response(
        status_code=302,
        headers={
            "Location": distribution.external_url,
            "X-Checksum-SHA256": distribution.sha256,
            "X-Expected-Size": str(distribution.size),
        },
    )


@router.get("/packages/{name}/{version}/download")
async def download_best_distribution(
    name: str,
    version: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    platform: str | None = Query(
        None, description="Platform tag to filter by (e.g., py3-none-any, cp311-cp311-win_amd64)"
    ),
) -> Response:
    """Redirect to external URL for the best matching distribution.

    In the registry model, the registry does NOT serve files directly.
    Instead, it redirects to the external URL where the file is hosted.

    When multiple platform variants exist, returns the most specific compatible variant.
    If a platform tag is specified, returns the best match for that platform.

    Returns a redirect with SHA256 checksum in X-Checksum-SHA256 header.
    Clients should verify the checksum after downloading from the external URL.
    """
    # Find the version and distributions
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

    if not ver.distributions:
        raise VersionNotFoundError(name, version)

    # Filter to only active distributions
    active_distributions = [d for d in ver.distributions if d.url_status == "active"]
    if not active_distributions:
        raise VersionNotFoundError(name, version)

    # Select the best distribution for the requested platform
    distribution = _select_best_distribution(active_distributions, platform)

    if distribution is None:
        raise VersionNotFoundError(name, version)

    # Redirect to external URL with checksum header for client verification
    return Response(
        status_code=302,
        headers={
            "Location": distribution.external_url,
            "X-Checksum-SHA256": distribution.sha256,
            "X-Expected-Size": str(distribution.size),
            "X-Filename": distribution.filename,
        },
    )
