# SPDX-License-Identifier: MIT
"""API token authentication for package uploads."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..middleware.errors import ForbiddenError, UnauthorizedError


@dataclass
class TokenInfo:
    """Information about an authenticated API token."""

    token_id: str
    user_id: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None = None


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user from any auth method."""

    user_id: str
    auth_type: str  # "api_token" or "trusted_publisher"
    scopes: list[str]
    # For trusted publishers
    github_repository: str | None = None
    github_workflow: str | None = None
    github_commit: str | None = None


def generate_api_token() -> tuple[str, str]:
    """Generate a new API token.

    Returns:
        Tuple of (token, token_hash) where token is the plaintext token
        to give to the user and token_hash is what we store in the database.
    """
    # Generate a secure random token
    token = f"apw_{secrets.token_urlsafe(32)}"
    # Hash it for storage
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def hash_token(token: str) -> str:
    """Hash a token for comparison with stored hash."""
    return hashlib.sha256(token.encode()).hexdigest()


def parse_authorization_header(auth_header: str | None) -> str | None:
    """Parse the Authorization header to extract the token.

    Supports:
    - Bearer <token>
    - Token <token>
    - <token> (raw token)

    Returns:
        The extracted token or None if header is missing/invalid.
    """
    if not auth_header:
        return None

    auth_header = auth_header.strip()

    # Handle "Bearer <token>" format
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    # Handle "Token <token>" format
    if auth_header.lower().startswith("token "):
        return auth_header[6:].strip()

    # Handle raw token (must start with apw_ prefix)
    if auth_header.startswith("apw_"):
        return auth_header

    return None


async def validate_api_token(
    token: str,
    session: AsyncSession,
) -> TokenInfo | None:
    """Validate an API token against the database.

    Args:
        token: The plaintext API token
        session: Database session

    Returns:
        TokenInfo if valid, None otherwise
    """
    from ..db.models import APIToken

    token_hash = hash_token(token)

    query = select(APIToken).where(
        APIToken.token_hash == token_hash,
        APIToken.revoked == False,  # noqa: E712
    )
    result = await session.execute(query)
    db_token = result.scalar_one_or_none()

    if db_token is None:
        return None

    # Check expiration
    if db_token.expires_at and db_token.expires_at < datetime.now(timezone.utc):
        return None

    # Update last used timestamp
    db_token.last_used_at = datetime.now(timezone.utc)
    await session.commit()

    return TokenInfo(
        token_id=str(db_token.id),
        user_id=db_token.user_id,
        scopes=db_token.scopes.split(",") if db_token.scopes else ["upload"],
        created_at=db_token.created_at,
        last_used_at=db_token.last_used_at,
    )


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> AuthenticatedUser:
    """FastAPI dependency to get the current authenticated user.

    Checks for API token authentication first, then falls back to
    Trusted Publisher OIDC if configured.

    Raises:
        UnauthorizedError: If no valid authentication is provided
    """
    # Try API token authentication
    token = parse_authorization_header(authorization)
    if token:
        token_info = await validate_api_token(token, session)
        if token_info:
            return AuthenticatedUser(
                user_id=token_info.user_id,
                auth_type="api_token",
                scopes=token_info.scopes,
            )
        raise UnauthorizedError("Invalid or expired API token")

    # Try Trusted Publisher OIDC (if configured)
    config = request.app.state.config
    if config.auth.oidc_enabled:
        from .oidc import validate_oidc_token

        oidc_user = await validate_oidc_token(request, session)
        if oidc_user:
            return oidc_user

    raise UnauthorizedError("Authentication required")


async def get_optional_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> AuthenticatedUser | None:
    """FastAPI dependency to optionally get the current user.

    Returns None if no authentication is provided, rather than raising an error.
    """
    try:
        return await get_current_user(request, authorization, session)
    except UnauthorizedError:
        return None


def require_scope(required_scope: str):
    """Create a dependency that requires a specific scope.

    Usage:
        @router.post("/packages/{name}/upload")
        async def upload(user: Annotated[AuthenticatedUser, Depends(require_scope("upload"))]):
            ...
    """

    async def check_scope(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if required_scope not in user.scopes and "*" not in user.scopes:
            raise ForbiddenError(f"Missing required scope: {required_scope}")
        return user

    return check_scope
