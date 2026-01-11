# SPDX-License-Identifier: MIT
"""Package management endpoints (yank, collaborators).

Note: The upload endpoint has been removed as part of the migration to
the registry-only model. Use the /register endpoint instead to register
packages with external URLs.
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    AuthenticatedUser,
    require_scope,
)
from ..db import create_audit_log, get_session
from ..db.models import (
    Package,
    Publisher,
    Version,
)
from ..middleware.errors import (
    ForbiddenError,
    PackageNotFoundError,
    VersionNotFoundError,
)

router = APIRouter()


class YankRequest(BaseModel):
    """Request body for yanking a version."""

    reason: str = ""


class CollaboratorRequest(BaseModel):
    """Request body for adding/removing collaborators."""

    user_id: str
    publisher_type: str = "user"  # "user" or "trusted_publisher"
    github_repository: str | None = None
    github_workflow: str | None = None


async def check_package_ownership(
    package_name: str,
    user: AuthenticatedUser,
    session: AsyncSession,
) -> Package | None:
    """Check if user owns or can publish to a package.

    Returns the package if it exists and user has access, None if package doesn't exist.
    Raises ForbiddenError if package exists but user doesn't have access.
    """
    from ..auth import require_trusted_publisher_for_package

    query = select(Package).where(Package.name == package_name)
    result = await session.execute(query)
    package = result.scalar_one_or_none()

    if package is None:
        return None

    # Check if user is a publisher for this package
    pub_query = select(Publisher).where(
        Publisher.package_name == package_name,
        Publisher.publisher_id == user.user_id,
    )
    pub_result = await session.execute(pub_query)
    publisher = pub_result.scalar_one_or_none()

    if publisher is None:
        # For trusted publishers, also check by repository
        if user.auth_type == "trusted_publisher" and user.github_repository:
            await require_trusted_publisher_for_package(user, package_name, session)
        else:
            raise ForbiddenError(f"Not authorized to publish to package '{package_name}'")

    return package


async def _create_audit_log_from_user(
    session: AsyncSession,
    package_name: str,
    action: str,
    user: AuthenticatedUser,
    version: str | None = None,
    details: dict | None = None,
) -> None:
    """Create an audit log entry from an authenticated user."""
    await create_audit_log(
        session=session,
        package_name=package_name,
        action=action,
        actor_id=user.user_id,
        actor_type=user.auth_type,
        version=version,
        details=details,
        github_repository=user.github_repository,
        github_workflow=user.github_workflow,
        github_commit=user.github_commit,
    )


@router.delete("/packages/{name}/{version}/yank")
async def yank_version(
    name: str,
    version: str,
    user: Annotated[AuthenticatedUser, Depends(require_scope("upload"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    body: YankRequest = Body(default=YankRequest()),
):
    """Yank (soft-delete) a version.

    Yanked versions are still downloadable but marked as deprecated.
    Requires authentication and package ownership.
    """
    # Check package exists and user has access
    package = await check_package_ownership(name, user, session)
    if package is None:
        raise PackageNotFoundError(name)

    # Find the version
    version_query = select(Version).where(
        Version.package_name == name,
        Version.version == version,
    )
    result = await session.execute(version_query)
    db_version = result.scalar_one_or_none()

    if db_version is None:
        raise VersionNotFoundError(name, version)

    if db_version.yanked:
        return {"message": f"Version {version} is already yanked"}

    # Yank the version
    db_version.yanked = True
    db_version.yank_reason = body.reason

    # Create audit log
    await _create_audit_log_from_user(
        session,
        name,
        "yank",
        user,
        version=version,
        details={"reason": body.reason},
    )

    await session.commit()

    return {"message": f"Successfully yanked {name} version {version}"}


@router.post("/packages/{name}/collaborators")
async def add_collaborator(
    name: str,
    collaborator: CollaboratorRequest,
    user: Annotated[AuthenticatedUser, Depends(require_scope("upload"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Add a collaborator to a package.

    Only package owners can add collaborators.
    """
    # Check package exists
    package_query = select(Package).where(Package.name == name)
    result = await session.execute(package_query)
    package = result.scalar_one_or_none()

    if package is None:
        raise PackageNotFoundError(name)

    # Check user is owner
    owner_query = select(Publisher).where(
        Publisher.package_name == name,
        Publisher.publisher_id == user.user_id,
        Publisher.is_owner == True,  # noqa: E712
    )
    owner_result = await session.execute(owner_query)
    owner = owner_result.scalar_one_or_none()

    if owner is None:
        raise ForbiddenError("Only package owners can add collaborators")

    # Check collaborator doesn't already exist
    existing_query = select(Publisher).where(
        Publisher.package_name == name,
        Publisher.publisher_id == collaborator.user_id,
    )
    existing_result = await session.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        return {"message": f"User {collaborator.user_id} is already a collaborator"}

    # Add collaborator
    new_publisher = Publisher(
        package_name=name,
        publisher_id=collaborator.user_id,
        publisher_type=collaborator.publisher_type,
        is_owner=False,
        github_repository=collaborator.github_repository,
        github_workflow=collaborator.github_workflow,
    )
    session.add(new_publisher)

    # Create audit log
    await _create_audit_log_from_user(
        session,
        name,
        "add_collaborator",
        user,
        details={
            "collaborator_id": collaborator.user_id,
            "collaborator_type": collaborator.publisher_type,
        },
    )

    await session.commit()

    return {"message": f"Successfully added {collaborator.user_id} as collaborator"}


@router.delete("/packages/{name}/collaborators/{collaborator_id}")
async def remove_collaborator(
    name: str,
    collaborator_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_scope("upload"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Remove a collaborator from a package.

    Only package owners can remove collaborators.
    Cannot remove the last owner.
    """
    # Check package exists
    package_query = select(Package).where(Package.name == name)
    result = await session.execute(package_query)
    package = result.scalar_one_or_none()

    if package is None:
        raise PackageNotFoundError(name)

    # Check user is owner
    owner_query = select(Publisher).where(
        Publisher.package_name == name,
        Publisher.publisher_id == user.user_id,
        Publisher.is_owner == True,  # noqa: E712
    )
    owner_result = await session.execute(owner_query)
    owner = owner_result.scalar_one_or_none()

    if owner is None:
        raise ForbiddenError("Only package owners can remove collaborators")

    # Find the collaborator
    collab_query = select(Publisher).where(
        Publisher.package_name == name,
        Publisher.publisher_id == collaborator_id,
    )
    collab_result = await session.execute(collab_query)
    collaborator = collab_result.scalar_one_or_none()

    if collaborator is None:
        return {"message": f"User {collaborator_id} is not a collaborator"}

    # Don't allow removing the last owner
    if collaborator.is_owner:
        owner_count_query = select(Publisher).where(
            Publisher.package_name == name,
            Publisher.is_owner == True,  # noqa: E712
        )
        owner_count_result = await session.execute(owner_count_query)
        owners = owner_count_result.scalars().all()

        if len(owners) <= 1:
            raise ForbiddenError("Cannot remove the last owner of a package")

    # Remove collaborator
    await session.delete(collaborator)

    # Create audit log
    await _create_audit_log_from_user(
        session,
        name,
        "remove_collaborator",
        user,
        details={"collaborator_id": collaborator_id},
    )

    await session.commit()

    return {"message": f"Successfully removed {collaborator_id} as collaborator"}


@router.get("/packages/{name}/collaborators")
async def list_collaborators(
    name: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """List all collaborators for a package."""
    # Check package exists
    package_query = select(Package).where(Package.name == name)
    result = await session.execute(package_query)
    package = result.scalar_one_or_none()

    if package is None:
        raise PackageNotFoundError(name)

    # Get all publishers
    pub_query = select(Publisher).where(Publisher.package_name == name)
    pub_result = await session.execute(pub_query)
    publishers = pub_result.scalars().all()

    return {
        "package": name,
        "collaborators": [
            {
                "user_id": p.publisher_id,
                "type": p.publisher_type,
                "is_owner": p.is_owner,
                "github_repository": p.github_repository,
                "added_at": p.added_at.isoformat() if p.added_at else None,
            }
            for p in publishers
        ],
    }
