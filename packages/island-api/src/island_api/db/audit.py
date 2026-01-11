# SPDX-License-Identifier: MIT
"""Audit logging for package modifications."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog


class AuditAction:
    """Standard audit action types."""

    CREATE_PACKAGE = "create_package"
    UPLOAD = "upload"
    YANK = "yank"
    UNYANK = "unyank"
    ADD_COLLABORATOR = "add_collaborator"
    REMOVE_COLLABORATOR = "remove_collaborator"
    TRANSFER_OWNERSHIP = "transfer_ownership"
    DELETE_PACKAGE = "delete_package"
    UPDATE_METADATA = "update_metadata"


async def create_audit_log(
    session: AsyncSession,
    package_name: str,
    action: str,
    actor_id: str,
    actor_type: str,
    version: str | None = None,
    details: dict[str, Any] | None = None,
    github_repository: str | None = None,
    github_workflow: str | None = None,
    github_commit: str | None = None,
) -> AuditLog:
    """Create an audit log entry for a package modification.

    Args:
        session: Database session
        package_name: Name of the package being modified
        action: Type of action (use AuditAction constants)
        actor_id: ID of the user or system performing the action
        actor_type: Type of actor ("user" or "trusted_publisher")
        version: Package version if applicable
        details: Additional details as a dictionary
        github_repository: GitHub repository for trusted publishers
        github_workflow: GitHub workflow for trusted publishers
        github_commit: GitHub commit SHA for trusted publishers

    Returns:
        The created AuditLog entry
    """
    log = AuditLog(
        package_name=package_name,
        version=version,
        action=action,
        actor_id=actor_id,
        actor_type=actor_type,
        timestamp=datetime.now(UTC),
        details=json.dumps(details) if details else None,
        github_repository=github_repository,
        github_workflow=github_workflow,
        github_commit=github_commit,
    )
    session.add(log)
    return log


async def get_package_audit_logs(
    session: AsyncSession,
    package_name: str,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Get audit logs for a specific package.

    Args:
        session: Database session
        package_name: Name of the package
        limit: Maximum number of logs to return
        offset: Number of logs to skip

    Returns:
        List of AuditLog entries ordered by timestamp descending
    """
    query = (
        select(AuditLog)
        .where(AuditLog.package_name == package_name)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_version_audit_logs(
    session: AsyncSession,
    package_name: str,
    version: str,
) -> list[AuditLog]:
    """Get audit logs for a specific package version.

    Args:
        session: Database session
        package_name: Name of the package
        version: Version string

    Returns:
        List of AuditLog entries for the version
    """
    query = (
        select(AuditLog)
        .where(
            AuditLog.package_name == package_name,
            AuditLog.version == version,
        )
        .order_by(AuditLog.timestamp.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_actor_audit_logs(
    session: AsyncSession,
    actor_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Get audit logs for a specific actor.

    Args:
        session: Database session
        actor_id: ID of the actor
        limit: Maximum number of logs to return
        offset: Number of logs to skip

    Returns:
        List of AuditLog entries for the actor
    """
    query = (
        select(AuditLog)
        .where(AuditLog.actor_id == actor_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_recent_audit_logs(
    session: AsyncSession,
    limit: int = 100,
    action_filter: str | None = None,
) -> list[AuditLog]:
    """Get recent audit logs across all packages.

    Args:
        session: Database session
        limit: Maximum number of logs to return
        action_filter: Optional filter by action type

    Returns:
        List of recent AuditLog entries
    """
    query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)

    if action_filter:
        query = query.where(AuditLog.action == action_filter)

    result = await session.execute(query)
    return list(result.scalars().all())


def parse_audit_details(log: AuditLog) -> dict[str, Any] | None:
    """Parse the JSON details field of an audit log.

    Args:
        log: AuditLog entry

    Returns:
        Parsed details dictionary or None
    """
    if log.details:
        try:
            return json.loads(log.details)
        except json.JSONDecodeError:
            return None
    return None
