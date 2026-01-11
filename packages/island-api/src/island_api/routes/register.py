# SPDX-License-Identifier: MIT
"""Package registration endpoints for the registry-only model.

This module implements the registration API where packages are registered
with external URLs (e.g., GitHub Releases) rather than uploaded directly.
The registry stores only metadata and URLs, not the actual package files.
"""

import hashlib
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import AuthenticatedUser, require_scope
from ..db import create_audit_log, get_session
from ..db.models import (
    Author,
    Distribution,
    Keyword,
    Package,
    PackageEntryPoint,
    Publisher,
    Version,
)
from ..middleware.errors import ForbiddenError, VersionExistsError
from ..models.registration import (
    DistributionRegistration,
    PackageRegistration,
    RegistrationResponse,
)

router = APIRouter()

# HTTP client timeout settings
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class URLValidationError(HTTPException):
    """Raised when URL validation fails."""

    def __init__(self, url: str, reason: str):
        super().__init__(
            status_code=400,
            detail=f"URL validation failed for {url}: {reason}",
        )


class ChecksumMismatchError(HTTPException):
    """Raised when checksum verification fails."""

    def __init__(self, filename: str, expected: str, actual: str):
        super().__init__(
            status_code=400,
            detail=f"Checksum mismatch for {filename}: expected {expected}, got {actual}",
        )


class SizeMismatchError(HTTPException):
    """Raised when file size verification fails."""

    def __init__(self, filename: str, expected: int, actual: int):
        super().__init__(
            status_code=400,
            detail=f"Size mismatch for {filename}: expected {expected} bytes, got {actual} bytes",
        )


async def verify_url_accessible(client: httpx.AsyncClient, url: HttpUrl) -> None:
    """Verify that a URL is accessible via HTTP HEAD request.

    Args:
        client: HTTP client to use for the request
        url: URL to verify

    Raises:
        URLValidationError: If the URL is not accessible or returns non-2xx status
    """
    url_str = str(url)

    # Verify URL uses HTTPS
    if not url_str.startswith("https://"):
        raise URLValidationError(url_str, "URL must use HTTPS scheme")

    try:
        response = await client.head(url_str, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise URLValidationError(url_str, "Request timed out") from e
    except httpx.ConnectError as e:
        raise URLValidationError(url_str, "Could not connect to server") from e
    except httpx.HTTPStatusError as e:
        raise URLValidationError(url_str, f"HTTP {e.response.status_code} response") from e
    except httpx.HTTPError as e:
        raise URLValidationError(url_str, str(e)) from e


async def download_and_verify_checksum(
    client: httpx.AsyncClient,
    dist: DistributionRegistration,
) -> None:
    """Download asset and verify its SHA256 checksum and size.

    Args:
        client: HTTP client to use for the request
        dist: Distribution registration containing URL, expected checksum, and size

    Raises:
        URLValidationError: If the download fails
        ChecksumMismatchError: If the checksum doesn't match
        SizeMismatchError: If the file size doesn't match
    """
    url_str = str(dist.url)

    try:
        response = await client.get(url_str, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise URLValidationError(url_str, "Download timed out") from e
    except httpx.ConnectError as e:
        raise URLValidationError(url_str, "Could not connect to server") from e
    except httpx.HTTPStatusError as e:
        raise URLValidationError(url_str, f"HTTP {e.response.status_code} response") from e
    except httpx.HTTPError as e:
        raise URLValidationError(url_str, str(e)) from e

    content = response.content

    # Verify size
    actual_size = len(content)
    if actual_size != dist.size:
        raise SizeMismatchError(dist.filename, dist.size, actual_size)

    # Verify checksum
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != dist.sha256:
        raise ChecksumMismatchError(dist.filename, dist.sha256, actual_sha256)


async def verify_distribution(
    client: httpx.AsyncClient,
    dist: DistributionRegistration,
) -> None:
    """Verify a distribution URL is accessible and checksum matches.

    This performs two-phase verification:
    1. HEAD request to verify URL is accessible
    2. GET request to download and verify checksum

    Args:
        client: HTTP client to use for requests
        dist: Distribution registration to verify

    Raises:
        URLValidationError: If URL is not accessible
        ChecksumMismatchError: If checksum doesn't match
        SizeMismatchError: If size doesn't match
    """
    # First verify URL is accessible with HEAD request
    await verify_url_accessible(client, dist.url)

    # Then download and verify checksum
    await download_and_verify_checksum(client, dist)


async def verify_package_ownership(
    session: AsyncSession,
    package_name: str,
    user: AuthenticatedUser,
) -> Package | None:
    """Verify user is authorized to publish to a package.

    Args:
        session: Database session
        package_name: Name of the package
        user: Authenticated user making the request

    Returns:
        The Package if it exists and user has access, None if package doesn't exist

    Raises:
        ForbiddenError: If package exists but user doesn't have access
    """
    # Check if package exists
    query = select(Package).where(Package.name == package_name)
    result = await session.execute(query)
    package = result.scalar_one_or_none()

    if package is None:
        # Package doesn't exist - first publisher will become owner
        return None

    # Check if user is a publisher for this package
    pub_query = select(Publisher).where(
        Publisher.package_name == package_name,
        Publisher.publisher_id == user.user_id,
    )
    pub_result = await session.execute(pub_query)
    publisher = pub_result.scalar_one_or_none()

    if publisher is not None:
        return package

    # For trusted publishers, also check by repository
    if user.auth_type == "trusted_publisher" and user.github_repository:
        repo_query = select(Publisher).where(
            Publisher.package_name == package_name,
            Publisher.github_repository == user.github_repository,
        )
        repo_result = await session.execute(repo_query)
        repo_publisher = repo_result.scalar_one_or_none()

        if repo_publisher is not None:
            return package

    raise ForbiddenError(f"Not authorized to publish to package '{package_name}'")


async def upsert_package(
    session: AsyncSession,
    registration: PackageRegistration,
    user: AuthenticatedUser,
) -> Package:
    """Create or update a package record.

    Args:
        session: Database session
        registration: Package registration data
        user: Authenticated user making the request

    Returns:
        The created or existing Package
    """
    # Check if package exists
    query = select(Package).where(Package.name == registration.name)
    result = await session.execute(query)
    package = result.scalar_one_or_none()

    if package is not None:
        # Update existing package metadata
        package.description = registration.description
        if registration.homepage:
            package.homepage = registration.homepage
        if registration.repository:
            package.repository = registration.repository
        if registration.license:
            package.license = registration.license
        return package

    # Create new package
    package = Package(
        name=registration.name,
        display_name=registration.game,
        description=registration.description,
        license=registration.license,
        homepage=registration.homepage,
        repository=registration.repository,
    )
    session.add(package)

    # Add user as owner
    owner = Publisher(
        package_name=registration.name,
        publisher_id=user.user_id,
        publisher_type=user.auth_type,
        is_owner=True,
        github_repository=user.github_repository,
        github_workflow=user.github_workflow,
    )
    session.add(owner)

    # Add authors
    for author_name in registration.authors:
        author = Author(package_name=registration.name, name=author_name)
        session.add(author)

    # Add keywords
    for kw in registration.keywords:
        keyword = Keyword(package_name=registration.name, keyword=kw)
        session.add(keyword)

    await create_audit_log(
        session=session,
        package_name=registration.name,
        action="create_package",
        actor_id=user.user_id,
        actor_type=user.auth_type,
        details={"owner": user.user_id},
        github_repository=user.github_repository,
        github_workflow=user.github_workflow,
        github_commit=user.github_commit,
    )

    return package


async def create_version(
    session: AsyncSession,
    package: Package,
    registration: PackageRegistration,
) -> Version:
    """Create a new version record.

    Args:
        session: Database session
        package: Parent package
        registration: Package registration data

    Returns:
        The created Version

    Raises:
        VersionExistsError: If version already exists
    """
    # Check version doesn't already exist
    version_query = select(Version).where(
        Version.package_name == package.name,
        Version.version == registration.version,
    )
    version_result = await session.execute(version_query)
    existing = version_result.scalar_one_or_none()

    if existing is not None:
        raise VersionExistsError(package.name, registration.version)

    # Create version record
    version = Version(
        package_name=package.name,
        version=registration.version,
        game=registration.game,
        minimum_ap_version=registration.minimum_ap_version,
        maximum_ap_version=registration.maximum_ap_version,
        pure_python=True,  # Default, could be determined from platform tags
    )
    session.add(version)
    await session.flush()  # Get version.id

    return version


async def create_distribution(
    session: AsyncSession,
    version: Version,
    dist: DistributionRegistration,
) -> Distribution:
    """Create a distribution record.

    Args:
        session: Database session
        version: Parent version
        dist: Distribution registration data

    Returns:
        The created Distribution
    """
    distribution = Distribution(
        version_id=version.id,
        filename=dist.filename,
        sha256=dist.sha256,
        size=dist.size,
        platform_tag=dist.platform_tag,
        external_url=str(dist.url),
    )
    session.add(distribution)
    return distribution


async def create_entry_points(
    session: AsyncSession,
    package_name: str,
    version: Version,
    entry_points: dict[str, str],
) -> None:
    """Create entry point records.

    Args:
        session: Database session
        package_name: Package name
        version: Parent version
        entry_points: Dictionary of entry point name -> module:attr
    """
    for ep_name, ep_value in entry_points.items():
        # Parse module:attr format
        if ":" in ep_value:
            module, attr = ep_value.rsplit(":", 1)
        else:
            module = ep_value
            attr = ""

        entry_point = PackageEntryPoint(
            package_name=package_name,
            version_id=version.id,
            entry_point_type="ap-island",
            name=ep_name,
            module=module,
            attr=attr,
        )
        session.add(entry_point)


@router.post("/register", response_model=RegistrationResponse)
async def register_package(
    registration: PackageRegistration,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_scope("upload"))],
) -> RegistrationResponse:
    """Register a package version with external asset URLs.

    This endpoint registers package metadata and external URLs.
    The registry does NOT store the actual package files.

    Before accepting registration:
    1. Validates the caller is authorized to publish this package
    2. Verifies each URL is accessible (HTTP HEAD request)
    3. Downloads each asset and verifies the SHA256 checksum matches

    If any verification fails, the registration is rejected.

    Args:
        registration: Package registration request
        session: Database session
        user: Authenticated user

    Returns:
        Registration response with package details

    Raises:
        HTTPException: If validation fails
        ForbiddenError: If user is not authorized
        VersionExistsError: If version already exists
    """
    # Verify authorization
    await verify_package_ownership(session, registration.name, user)

    # Verify all URLs and checksums
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for dist in registration.distributions:
            await verify_distribution(client, dist)

    # Create/update package
    package = await upsert_package(session, registration, user)

    # Create version
    version = await create_version(session, package, registration)

    # Create distributions
    for dist in registration.distributions:
        await create_distribution(session, version, dist)

    # Create entry points
    await create_entry_points(
        session,
        registration.name,
        version,
        registration.entry_points,
    )

    # Create audit log
    await create_audit_log(
        session=session,
        package_name=registration.name,
        action="register",
        actor_id=user.user_id,
        actor_type=user.auth_type,
        version=registration.version,
        details={
            "distributions": [d.filename for d in registration.distributions],
            "source_repository": registration.source_repository,
            "source_commit": registration.source_commit,
        },
        github_repository=user.github_repository,
        github_workflow=user.github_workflow,
        github_commit=user.github_commit,
    )

    await session.commit()

    return RegistrationResponse(
        package_name=registration.name,
        version=registration.version,
        registered_distributions=[d.filename for d in registration.distributions],
        registry_url=f"/v1/island/packages/{registration.name}/{registration.version}",
    )
