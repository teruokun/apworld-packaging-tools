# SPDX-License-Identifier: MIT
"""Package listing, search, and metadata endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_session
from ..db.models import Author, Keyword, Package, Version
from ..middleware.errors import PackageNotFoundError, VersionNotFoundError
from ..models.package import (
    AuthorModel,
    DistributionModel,
    DownloadStats,
    PackageListItem,
    PackageMetadata,
    VersionListItem,
    VersionMetadata,
)
from ..models.responses import (
    IndexPackageEntry,
    IndexResponse,
    PackageListResponse,
    PaginationInfo,
    SearchResponse,
    VersionListResponse,
)

router = APIRouter()


def _build_download_url(name: str, version: str, filename: str) -> str:
    """Build download URL for a distribution."""
    return f"/v1/packages/{name}/{version}/download/{filename}"


def _package_to_list_item(package: Package, latest_version: str | None = None) -> PackageListItem:
    """Convert Package model to PackageListItem."""
    return PackageListItem(
        name=package.name,
        display_name=package.display_name,
        description=package.description,
        latest_version=latest_version,
        downloads=DownloadStats(total=package.total_downloads, recent=0),
    )


@router.get("/packages", response_model=PackageListResponse)
async def list_packages(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
) -> PackageListResponse:
    """List all packages with pagination.

    Returns a paginated list of all packages in the repository,
    sorted by name alphabetically.
    """
    # Count total packages
    count_query = select(func.count()).select_from(Package)
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get packages with pagination
    offset = (page - 1) * per_page
    packages_query = (
        select(Package)
        .options(selectinload(Package.versions))
        .order_by(Package.name)
        .offset(offset)
        .limit(per_page)
    )
    result = await session.execute(packages_query)
    packages = result.scalars().all()

    # Build response
    package_items = []
    for pkg in packages:
        # Find latest non-yanked version
        latest = None
        if pkg.versions:
            non_yanked = [v for v in pkg.versions if not v.yanked]
            if non_yanked:
                # Sort by published_at descending
                non_yanked.sort(key=lambda v: v.published_at, reverse=True)
                latest = non_yanked[0].version

        package_items.append(_package_to_list_item(pkg, latest))

    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return PackageListResponse(
        packages=package_items,
        pagination=PaginationInfo(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get("/search", response_model=SearchResponse)
async def search_packages(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query("", description="Search query"),
    game: str | None = Query(None, description="Filter by game name"),
    author: str | None = Query(None, description="Filter by author name"),
    compatible_with: str | None = Query(
        None, description="Filter by Core AP version compatibility"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
) -> SearchResponse:
    """Search packages by name, keyword, author, or game.

    Supports filtering by:
    - q: Free text search across name, display_name, description, and keywords
    - game: Filter by game name (from version metadata)
    - author: Filter by author name
    - compatible_with: Filter by Core AP version compatibility
    """
    # Build base query
    query = select(Package).options(
        selectinload(Package.versions),
        selectinload(Package.authors),
        selectinload(Package.keywords),
    )

    conditions = []

    # Text search
    if q:
        search_term = f"%{q}%"
        # Search in package name, display_name, description
        text_conditions = [
            Package.name.ilike(search_term),
            Package.display_name.ilike(search_term),
            Package.description.ilike(search_term),
        ]
        # Also search in keywords via subquery
        keyword_subquery = (
            select(Keyword.package_name).where(Keyword.keyword.ilike(search_term)).distinct()
        )
        text_conditions.append(Package.name.in_(keyword_subquery))
        conditions.append(or_(*text_conditions))

    # Author filter
    if author:
        author_subquery = (
            select(Author.package_name).where(Author.name.ilike(f"%{author}%")).distinct()
        )
        conditions.append(Package.name.in_(author_subquery))

    # Game filter - requires joining with versions
    if game:
        game_subquery = (
            select(Version.package_name)
            .where(Version.game.ilike(f"%{game}%"))
            .where(Version.yanked == False)  # noqa: E712
            .distinct()
        )
        conditions.append(Package.name.in_(game_subquery))

    # Compatibility filter
    if compatible_with:
        # Find packages with versions compatible with the given AP version
        compat_subquery = (
            select(Version.package_name)
            .where(Version.yanked == False)  # noqa: E712
            .where(
                or_(
                    Version.minimum_ap_version.is_(None),
                    Version.minimum_ap_version <= compatible_with,
                )
            )
            .where(
                or_(
                    Version.maximum_ap_version.is_(None),
                    Version.maximum_ap_version >= compatible_with,
                )
            )
            .distinct()
        )
        conditions.append(Package.name.in_(compat_subquery))

    # Apply conditions
    if conditions:
        for condition in conditions:
            query = query.where(condition)

    # Count total results
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(Package.name).offset(offset).limit(per_page)

    result = await session.execute(query)
    packages = result.scalars().all()

    # Build response
    results = []
    for pkg in packages:
        latest = None
        if pkg.versions:
            non_yanked = [v for v in pkg.versions if not v.yanked]
            if non_yanked:
                non_yanked.sort(key=lambda v: v.published_at, reverse=True)
                latest = non_yanked[0].version
        results.append(_package_to_list_item(pkg, latest))

    return SearchResponse(
        results=results,
        query=q,
        filters={
            "game": game,
            "author": author,
            "compatible_with": compatible_with,
        },
        total=total,
    )


@router.get("/packages/{name}", response_model=PackageMetadata)
async def get_package(
    name: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PackageMetadata:
    """Get full metadata for a specific package.

    Returns detailed package information including all versions,
    authors, keywords, and download statistics.
    """
    query = (
        select(Package)
        .options(
            selectinload(Package.versions).selectinload(Version.distributions),
            selectinload(Package.authors),
            selectinload(Package.keywords),
        )
        .where(Package.name == name)
    )
    result = await session.execute(query)
    package = result.scalar_one_or_none()

    if package is None:
        raise PackageNotFoundError(name)

    # Build version list
    versions = []
    latest_version = None
    for v in sorted(package.versions, key=lambda x: x.published_at, reverse=True):
        versions.append(
            VersionListItem(
                version=v.version,
                published_at=v.published_at,
                yanked=v.yanked,
                pure_python=v.pure_python,
            )
        )
        if latest_version is None and not v.yanked:
            latest_version = v.version

    return PackageMetadata(
        name=package.name,
        display_name=package.display_name,
        description=package.description,
        license=package.license,
        homepage=package.homepage,
        repository=package.repository,
        created_at=package.created_at,
        updated_at=package.updated_at,
        authors=[AuthorModel(name=a.name, email=a.email) for a in package.authors],
        keywords=[k.keyword for k in package.keywords],
        latest_version=latest_version,
        versions=versions,
        downloads=DownloadStats(total=package.total_downloads, recent=0),
    )


@router.get("/packages/{name}/versions", response_model=VersionListResponse)
async def list_versions(
    name: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    include_yanked: bool = Query(False, description="Include yanked versions"),
) -> VersionListResponse:
    """List all versions of a package.

    Returns all versions sorted by publication date (newest first).
    By default, yanked versions are excluded.
    """
    # Check package exists
    pkg_query = select(Package).where(Package.name == name)
    pkg_result = await session.execute(pkg_query)
    package = pkg_result.scalar_one_or_none()

    if package is None:
        raise PackageNotFoundError(name)

    # Get versions
    versions_query = (
        select(Version).where(Version.package_name == name).order_by(Version.published_at.desc())
    )

    if not include_yanked:
        versions_query = versions_query.where(Version.yanked == False)  # noqa: E712

    result = await session.execute(versions_query)
    versions = result.scalars().all()

    return VersionListResponse(
        package_name=name,
        versions=[
            VersionListItem(
                version=v.version,
                published_at=v.published_at,
                yanked=v.yanked,
                pure_python=v.pure_python,
            )
            for v in versions
        ],
        total=len(versions),
    )


@router.get("/packages/{name}/{version}", response_model=VersionMetadata)
async def get_version(
    name: str,
    version: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VersionMetadata:
    """Get metadata for a specific version.

    Returns detailed version information including all distributions
    and their download URLs.
    """
    query = (
        select(Version)
        .options(selectinload(Version.distributions))
        .where(Version.package_name == name)
        .where(Version.version == version)
    )
    result = await session.execute(query)
    ver = result.scalar_one_or_none()

    if ver is None:
        # Check if package exists to give better error
        pkg_query = select(Package).where(Package.name == name)
        pkg_result = await session.execute(pkg_query)
        if pkg_result.scalar_one_or_none() is None:
            raise PackageNotFoundError(name)
        raise VersionNotFoundError(name, version)

    return VersionMetadata(
        version=ver.version,
        game=ver.game,
        minimum_ap_version=ver.minimum_ap_version,
        maximum_ap_version=ver.maximum_ap_version,
        pure_python=ver.pure_python,
        published_at=ver.published_at,
        yanked=ver.yanked,
        yank_reason=ver.yank_reason,
        distributions=[
            DistributionModel(
                filename=d.filename,
                sha256=d.sha256,
                size=d.size,
                platform_tag=d.platform_tag,
                download_url=_build_download_url(name, version, d.filename),
            )
            for d in ver.distributions
        ],
    )


@router.get("/index.json", response_model=IndexResponse)
async def get_index(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndexResponse:
    """Get full package index for offline tooling.

    Returns a complete index of all packages and versions,
    suitable for offline package resolution and caching.
    """
    query = select(Package).options(
        selectinload(Package.versions).selectinload(Version.distributions)
    )
    result = await session.execute(query)
    packages = result.scalars().all()

    index_packages: dict[str, IndexPackageEntry] = {}
    total_versions = 0

    for pkg in packages:
        versions_dict: dict[str, dict] = {}
        latest_version = None

        for v in sorted(pkg.versions, key=lambda x: x.published_at, reverse=True):
            total_versions += 1
            versions_dict[v.version] = {
                "game": v.game,
                "minimum_ap_version": v.minimum_ap_version,
                "maximum_ap_version": v.maximum_ap_version,
                "pure_python": v.pure_python,
                "published_at": v.published_at.isoformat(),
                "yanked": v.yanked,
                "distributions": [
                    {
                        "filename": d.filename,
                        "sha256": d.sha256,
                        "size": d.size,
                        "platform_tag": d.platform_tag,
                    }
                    for d in v.distributions
                ],
            }
            if latest_version is None and not v.yanked:
                latest_version = v.version

        index_packages[pkg.name] = IndexPackageEntry(
            display_name=pkg.display_name,
            description=pkg.description,
            latest_version=latest_version,
            versions=versions_dict,
        )

    return IndexResponse(
        packages=index_packages,
        generated_at=datetime.now(timezone.utc),
        total_packages=len(packages),
        total_versions=total_versions,
    )
