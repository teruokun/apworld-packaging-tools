# SPDX-License-Identifier: MIT
"""Package upload endpoints."""

import hashlib
import json
import zipfile
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    AuthenticatedUser,
    require_scope,
    require_trusted_publisher_for_package,
)
from ..db import create_audit_log, get_session
from ..db.models import (
    Author,
    Distribution,
    Keyword,
    Package,
    Publisher,
    Version,
)
from ..middleware.errors import (
    ErrorDetail,
    ForbiddenError,
    InvalidManifestError,
    InvalidVersionError,
    PackageNotFoundError,
    VersionExistsError,
    VersionNotFoundError,
)

router = APIRouter()


class UploadResponse(BaseModel):
    """Response for successful upload."""

    package: str
    version: str
    filename: str
    sha256: str
    message: str


class YankRequest(BaseModel):
    """Request body for yanking a version."""

    reason: str = ""


class CollaboratorRequest(BaseModel):
    """Request body for adding/removing collaborators."""

    user_id: str
    publisher_type: str = "user"  # "user" or "trusted_publisher"
    github_repository: str | None = None
    github_workflow: str | None = None


def compute_sha256(data: bytes) -> str:
    """Compute SHA256 hash of data."""
    return hashlib.sha256(data).hexdigest()


def validate_semver(version: str) -> bool:
    """Validate that a version string follows semver format."""
    import re

    pattern = (
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )
    return bool(re.match(pattern, version))


def extract_manifest_from_apworld(file_content: bytes) -> dict:
    """Extract and parse archipelago.json from an .apworld file."""
    try:
        with zipfile.ZipFile(BytesIO(file_content), "r") as zf:
            # Look for archipelago.json in the root or first directory
            manifest_paths = [n for n in zf.namelist() if n.endswith("archipelago.json")]
            if not manifest_paths:
                raise InvalidManifestError("No archipelago.json found in package")

            # Prefer root-level manifest
            manifest_path = min(manifest_paths, key=lambda p: p.count("/"))
            manifest_data = zf.read(manifest_path)
            return json.loads(manifest_data)
    except zipfile.BadZipFile as e:
        raise InvalidManifestError(f"Invalid .apworld file: {e}") from e
    except json.JSONDecodeError as e:
        raise InvalidManifestError(f"Invalid JSON in archipelago.json: {e}") from e


def validate_manifest(manifest: dict) -> list[ErrorDetail]:
    """Validate manifest against required schema."""
    errors = []

    # Required fields
    required_fields = ["game", "version", "compatible_version"]
    for field in required_fields:
        if field not in manifest:
            errors.append(ErrorDetail(field=field, error="Required field missing"))

    # Validate version field (schema version, must be integer)
    if "version" in manifest and not isinstance(manifest["version"], int):
        errors.append(ErrorDetail(field="version", error="Must be an integer"))

    # Validate world_version if present (semver)
    if "world_version" in manifest:
        if not validate_semver(manifest["world_version"]):
            errors.append(
                ErrorDetail(
                    field="world_version",
                    error="Must follow semantic versioning format",
                )
            )

    return errors


async def check_package_ownership(
    package_name: str,
    user: AuthenticatedUser,
    session: AsyncSession,
) -> Package | None:
    """Check if user owns or can publish to a package.

    Returns the package if it exists and user has access, None if package doesn't exist.
    Raises ForbiddenError if package exists but user doesn't have access.
    """
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


@router.post("/packages/{name}/upload", response_model=UploadResponse)
async def upload_package(
    name: str,
    file: UploadFile,
    user: Annotated[AuthenticatedUser, Depends(require_scope("upload"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    sha256_digest: Annotated[str | None, Query(alias="sha256")] = None,
):
    """Upload a new package version.

    Requires authentication with 'upload' scope.
    Validates manifest and checksums.
    First uploader becomes package owner.
    """
    # Read file content
    content = await file.read()

    # Verify checksum if provided
    computed_sha256 = compute_sha256(content)
    if sha256_digest and sha256_digest.lower() != computed_sha256.lower():
        raise InvalidManifestError(
            f"Checksum mismatch: expected {sha256_digest}, got {computed_sha256}",
            details=[
                ErrorDetail(
                    field="sha256",
                    error="Provided checksum does not match file content",
                )
            ],
        )

    # Extract and validate manifest
    manifest = extract_manifest_from_apworld(content)
    validation_errors = validate_manifest(manifest)
    if validation_errors:
        raise InvalidManifestError("Manifest validation failed", details=validation_errors)

    # Get version from manifest
    world_version = manifest.get("world_version", "0.0.1")
    if not validate_semver(world_version):
        raise InvalidVersionError(world_version)

    # Check package ownership or create new package
    package = await check_package_ownership(name, user, session)

    if package is None:
        # Create new package - first uploader becomes owner
        package = Package(
            name=name,
            display_name=manifest.get("game", name),
            description=manifest.get("description"),
            license=manifest.get("license"),
            homepage=manifest.get("homepage"),
            repository=manifest.get("repository"),
        )
        session.add(package)

        # Add user as owner
        owner = Publisher(
            package_name=name,
            publisher_id=user.user_id,
            publisher_type=user.auth_type,
            is_owner=True,
            github_repository=user.github_repository,
            github_workflow=user.github_workflow,
        )
        session.add(owner)

        # Add authors from manifest
        for author_name in manifest.get("authors", []):
            author = Author(package_name=name, name=author_name)
            session.add(author)

        # Add keywords from manifest
        for kw in manifest.get("keywords", []):
            keyword = Keyword(package_name=name, keyword=kw)
            session.add(keyword)

        await _create_audit_log_from_user(
            session, name, "create_package", user, details={"owner": user.user_id}
        )

    # Check version doesn't already exist (immutability)
    version_query = select(Version).where(
        Version.package_name == name,
        Version.version == world_version,
    )
    version_result = await session.execute(version_query)
    existing_version = version_result.scalar_one_or_none()

    if existing_version is not None:
        raise VersionExistsError(name, world_version)

    # Create version record
    version_record = Version(
        package_name=name,
        version=world_version,
        game=manifest.get("game", name),
        minimum_ap_version=manifest.get("minimum_ap_version"),
        maximum_ap_version=manifest.get("maximum_ap_version"),
        pure_python=manifest.get("pure_python", True),
    )
    session.add(version_record)
    await session.flush()  # Get version.id

    # Determine platform tag from filename or manifest
    filename = file.filename or f"{name}-{world_version}-py3-none-any.apworld"
    platform_tag = "py3-none-any"
    if "-" in filename:
        parts = filename.rsplit("-", 3)
        if len(parts) >= 4:
            platform_tag = f"{parts[-3]}-{parts[-2]}-{parts[-1].split('.')[0]}"

    # Create distribution record
    storage_path = f"packages/{name}/{world_version}/{filename}"
    distribution = Distribution(
        version_id=version_record.id,
        filename=filename,
        sha256=computed_sha256,
        size=len(content),
        platform_tag=platform_tag,
        storage_path=storage_path,
    )
    session.add(distribution)

    # Create audit log
    await _create_audit_log_from_user(
        session,
        name,
        "upload",
        user,
        version=world_version,
        details={
            "filename": filename,
            "sha256": computed_sha256,
            "size": len(content),
        },
    )

    await session.commit()

    # TODO: Actually store the file content to storage backend
    # This would be handled by a storage service in production

    return UploadResponse(
        package=name,
        version=world_version,
        filename=filename,
        sha256=computed_sha256,
        message=f"Successfully uploaded {name} version {world_version}",
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
