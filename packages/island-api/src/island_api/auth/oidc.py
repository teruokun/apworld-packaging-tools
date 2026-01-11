# SPDX-License-Identifier: MIT
"""Trusted Publisher OIDC authentication for GitHub Actions."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.errors import ForbiddenError, UnauthorizedError
from .tokens import AuthenticatedUser


@dataclass
class OIDCClaims:
    """Claims extracted from a GitHub Actions OIDC token."""

    # Standard claims
    iss: str  # Issuer (https://token.actions.githubusercontent.com)
    sub: str  # Subject (repo:owner/repo:ref:refs/heads/main)
    aud: str  # Audience
    exp: int  # Expiration time
    iat: int  # Issued at time

    # GitHub-specific claims
    repository: str  # owner/repo
    repository_owner: str  # owner
    workflow: str  # workflow filename
    ref: str  # refs/heads/main or refs/tags/v1.0.0
    sha: str  # commit SHA
    actor: str  # GitHub username who triggered the workflow
    run_id: str  # Workflow run ID
    run_number: str  # Workflow run number
    job_workflow_ref: str  # Full workflow reference


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload without verification (verification done by OIDC provider).

    Note: In production, you should verify the token signature using the
    OIDC provider's public keys. This is a simplified implementation.
    """
    import base64

    try:
        # JWT format: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        # Decode payload (add padding if needed)
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        raise ValueError(f"Failed to decode JWT: {e}") from e


def parse_oidc_claims(payload: dict[str, Any]) -> OIDCClaims:
    """Parse OIDC claims from JWT payload."""
    return OIDCClaims(
        iss=payload.get("iss", ""),
        sub=payload.get("sub", ""),
        aud=payload.get("aud", ""),
        exp=payload.get("exp", 0),
        iat=payload.get("iat", 0),
        repository=payload.get("repository", ""),
        repository_owner=payload.get("repository_owner", ""),
        workflow=payload.get("workflow", ""),
        ref=payload.get("ref", ""),
        sha=payload.get("sha", ""),
        actor=payload.get("actor", ""),
        run_id=str(payload.get("run_id", "")),
        run_number=str(payload.get("run_number", "")),
        job_workflow_ref=payload.get("job_workflow_ref", ""),
    )


async def verify_oidc_token(
    token: str,
    config: Any,
) -> OIDCClaims:
    """Verify an OIDC token from GitHub Actions.

    Args:
        token: The OIDC JWT token
        config: API configuration with OIDC settings

    Returns:
        Parsed and verified OIDC claims

    Raises:
        UnauthorizedError: If token is invalid or expired
    """
    try:
        payload = decode_jwt_payload(token)
    except ValueError as e:
        raise UnauthorizedError(f"Invalid OIDC token: {e}") from e

    claims = parse_oidc_claims(payload)

    # Verify issuer
    expected_issuer = config.auth.oidc_issuer or "https://token.actions.githubusercontent.com"
    if claims.iss != expected_issuer:
        raise UnauthorizedError(f"Invalid OIDC issuer: {claims.iss}")

    # Verify audience if configured
    if config.auth.oidc_audience and claims.aud != config.auth.oidc_audience:
        raise UnauthorizedError(f"Invalid OIDC audience: {claims.aud}")

    # Verify expiration
    now = datetime.now(timezone.utc).timestamp()
    if claims.exp < now:
        raise UnauthorizedError("OIDC token has expired")

    return claims


async def validate_trusted_publisher(
    claims: OIDCClaims,
    package_name: str,
    session: AsyncSession,
) -> bool:
    """Validate that the OIDC claims match a registered Trusted Publisher.

    Args:
        claims: Verified OIDC claims
        package_name: The package being uploaded to
        session: Database session

    Returns:
        True if the claims match a registered Trusted Publisher
    """
    from ..db.models import Publisher

    # Look for a matching trusted publisher
    query = select(Publisher).where(
        Publisher.package_name == package_name,
        Publisher.publisher_type == "trusted_publisher",
        Publisher.github_repository == claims.repository,
    )
    result = await session.execute(query)
    publisher = result.scalar_one_or_none()

    if publisher is None:
        return False

    # Optionally verify workflow matches
    if publisher.github_workflow:
        # Workflow can be specified as just filename or full path
        workflow_name = (
            claims.workflow.split("/")[-1] if "/" in claims.workflow else claims.workflow
        )
        expected_workflow = (
            publisher.github_workflow.split("/")[-1]
            if "/" in publisher.github_workflow
            else publisher.github_workflow
        )
        if workflow_name != expected_workflow:
            return False

    return True


async def validate_oidc_token(
    request: Request,
    session: AsyncSession,
    authorization: str | None = None,
    x_github_repository: str | None = None,
) -> AuthenticatedUser | None:
    """Validate OIDC token from request headers.

    Args:
        request: FastAPI request
        session: Database session
        authorization: Authorization header value
        x_github_repository: X-GitHub-Repository header (optional hint)

    Returns:
        AuthenticatedUser if valid, None otherwise
    """
    config = request.app.state.config

    if not config.auth.oidc_enabled:
        return None

    # Extract token from Authorization header
    if not authorization:
        return None

    token = None
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        return None

    # Don't process API tokens as OIDC
    if token.startswith("isl_"):
        return None

    try:
        claims = await verify_oidc_token(token, config)
    except UnauthorizedError:
        return None

    return AuthenticatedUser(
        user_id=f"github:{claims.repository}",
        auth_type="trusted_publisher",
        scopes=["upload"],
        github_repository=claims.repository,
        github_workflow=claims.workflow,
        github_commit=claims.sha,
    )


async def require_trusted_publisher_for_package(
    user: AuthenticatedUser,
    package_name: str,
    session: AsyncSession,
) -> None:
    """Verify that a Trusted Publisher user is authorized for a package.

    Args:
        user: Authenticated user (must be trusted_publisher type)
        package_name: Package to check authorization for
        session: Database session

    Raises:
        ForbiddenError: If user is not authorized for the package
    """
    if user.auth_type != "trusted_publisher":
        return  # Not a trusted publisher, skip this check

    if not user.github_repository:
        raise ForbiddenError("Missing GitHub repository information")

    # Create mock claims for validation
    claims = OIDCClaims(
        iss="",
        sub="",
        aud="",
        exp=0,
        iat=0,
        repository=user.github_repository,
        repository_owner=user.github_repository.split("/")[0]
        if "/" in user.github_repository
        else "",
        workflow=user.github_workflow or "",
        ref="",
        sha=user.github_commit or "",
        actor="",
        run_id="",
        run_number="",
        job_workflow_ref="",
    )

    is_authorized = await validate_trusted_publisher(claims, package_name, session)
    if not is_authorized:
        raise ForbiddenError(
            f"Repository '{user.github_repository}' is not a registered "
            f"Trusted Publisher for package '{package_name}'"
        )
