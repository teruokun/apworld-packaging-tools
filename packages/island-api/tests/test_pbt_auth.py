# SPDX-License-Identifier: MIT
"""Property-based tests for authentication and authorization.

These tests validate:
- Property 7: Authentication required for registration
- Property 8: Authorization verification

Feature: registry-model-migration
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from island_api.auth import AuthenticatedUser
from island_api.auth.tokens import (
    generate_api_token,
    get_current_user,
    hash_token,
    parse_authorization_header,
    require_scope,
    validate_api_token,
)
from island_api.db.models import APIToken, Package, Publisher
from island_api.middleware.errors import ForbiddenError, UnauthorizedError
from island_api.routes.register import verify_package_ownership


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid API token format
valid_api_token = st.from_regex(r"isl_[A-Za-z0-9_-]{32,64}", fullmatch=True)

# Invalid API token formats
invalid_api_token = st.one_of(
    st.from_regex(r"[A-Za-z0-9_-]{10,50}", fullmatch=True),  # Missing isl_ prefix
    st.from_regex(r"isl_[A-Za-z0-9]{1,10}", fullmatch=True),  # Too short
    st.just(""),  # Empty
    st.just("Bearer "),  # Just Bearer prefix
)


# Valid package names - use UUID suffix to ensure uniqueness across hypothesis iterations
def unique_package_name() -> st.SearchStrategy[str]:
    """Generate unique package names for each test iteration."""
    return st.builds(
        lambda base: f"{base}-{uuid.uuid4().hex[:8]}",
        st.from_regex(r"[a-z][a-z0-9]{2,10}", fullmatch=True),
    )


# Valid user IDs - use UUID suffix to ensure uniqueness
def unique_user_id() -> st.SearchStrategy[str]:
    """Generate unique user IDs for each test iteration."""
    return st.builds(
        lambda: f"user_{uuid.uuid4().hex[:16]}",
    )


# GitHub repository format - use UUID suffix to ensure uniqueness
def unique_github_repository() -> st.SearchStrategy[str]:
    """Generate unique GitHub repository names for each test iteration."""
    return st.builds(
        lambda: f"owner-{uuid.uuid4().hex[:6]}/repo-{uuid.uuid4().hex[:6]}",
    )


# Legacy strategies for non-database tests
valid_package_name = st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True)
valid_user_id = st.from_regex(r"user_[a-z0-9]{8,16}", fullmatch=True)
github_repository = st.from_regex(r"[a-z0-9\-]+/[a-z0-9\-]+", fullmatch=True)


# =============================================================================
# Property 7: Authentication required for registration
# Feature: registry-model-migration, Property 7: Authentication required for registration
# Validates: Requirements 3.1, 3.4
# =============================================================================


class TestAuthenticationRequired:
    """Property 7: Authentication required for registration tests.

    For any registration request, the registry SHALL require valid authentication.
    Unauthenticated requests SHALL be rejected with 401 status.
    """

    def test_parse_authorization_header_bearer(self):
        """Bearer token format is correctly parsed."""
        token = "isl_test_token_12345"
        result = parse_authorization_header(f"Bearer {token}")
        assert result == token

    def test_parse_authorization_header_token(self):
        """Token format is correctly parsed."""
        token = "isl_test_token_12345"
        result = parse_authorization_header(f"Token {token}")
        assert result == token

    def test_parse_authorization_header_raw(self):
        """Raw token with isl_ prefix is correctly parsed."""
        token = "isl_test_token_12345"
        result = parse_authorization_header(token)
        assert result == token

    def test_parse_authorization_header_none(self):
        """None header returns None."""
        result = parse_authorization_header(None)
        assert result is None

    def test_parse_authorization_header_empty(self):
        """Empty header returns None."""
        result = parse_authorization_header("")
        assert result is None

    @given(token=invalid_api_token)
    @settings(max_examples=100)
    def test_invalid_token_format_returns_none(self, token: str):
        """Property 7: Invalid token formats are not parsed as valid tokens.

        Feature: registry-model-migration, Property 7: Authentication required for registration
        Validates: Requirements 3.1, 3.4
        """
        # Tokens without isl_ prefix should return None (unless they have Bearer/Token prefix)
        if not token.startswith("isl_") and not token.lower().startswith(("bearer ", "token ")):
            result = parse_authorization_header(token)
            assert result is None


@pytest.mark.asyncio
class TestAPITokenValidation:
    """Tests for API token validation."""

    @given(user_id=st.builds(lambda: f"user_{uuid.uuid4().hex[:16]}"))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_valid_token_accepted(self, user_id: str, test_session: AsyncSession):
        """Property 7: Valid API tokens are accepted.

        Feature: registry-model-migration, Property 7: Authentication required for registration
        Validates: Requirements 3.1, 3.4
        """
        # Generate a token
        token, token_hash = generate_api_token()

        # Create token in database
        db_token = APIToken(
            token_hash=token_hash,
            user_id=user_id,
            scopes="upload",
            created_at=datetime.now(UTC),
        )
        test_session.add(db_token)
        await test_session.commit()

        # Validate the token
        result = await validate_api_token(token, test_session)

        assert result is not None
        assert result.user_id == user_id
        assert "upload" in result.scopes

    @given(token=valid_api_token)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_nonexistent_token_rejected(self, token: str, test_session: AsyncSession):
        """Property 7: Non-existent tokens are rejected.

        Feature: registry-model-migration, Property 7: Authentication required for registration
        Validates: Requirements 3.1, 3.4
        """
        # Token doesn't exist in database
        result = await validate_api_token(token, test_session)
        assert result is None

    @given(user_id=st.builds(lambda: f"user_{uuid.uuid4().hex[:16]}"))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_revoked_token_rejected(self, user_id: str, test_session: AsyncSession):
        """Property 7: Revoked tokens are rejected.

        Feature: registry-model-migration, Property 7: Authentication required for registration
        Validates: Requirements 3.1, 3.4
        """
        # Generate a token
        token, token_hash = generate_api_token()

        # Create revoked token in database
        db_token = APIToken(
            token_hash=token_hash,
            user_id=user_id,
            scopes="upload",
            created_at=datetime.now(UTC),
            revoked=True,
        )
        test_session.add(db_token)
        await test_session.commit()

        # Validate the token - should be rejected
        result = await validate_api_token(token, test_session)
        assert result is None


@pytest.mark.asyncio
class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    async def test_missing_auth_raises_unauthorized(self, app):
        """Property 7: Missing authentication raises UnauthorizedError.

        Feature: registry-model-migration, Property 7: Authentication required for registration
        Validates: Requirements 3.1, 3.4
        """
        # Create mock request
        mock_request = MagicMock()
        mock_request.app = app
        mock_session = AsyncMock(spec=AsyncSession)

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(mock_request, None, mock_session)

        assert "Authentication required" in str(exc_info.value.message)

    async def test_invalid_token_raises_unauthorized(self, app, test_session: AsyncSession):
        """Property 7: Invalid token raises UnauthorizedError.

        Feature: registry-model-migration, Property 7: Authentication required for registration
        Validates: Requirements 3.1, 3.4
        """
        mock_request = MagicMock()
        mock_request.app = app

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(
                mock_request,
                "Bearer isl_invalid_token_that_does_not_exist",
                test_session,
            )

        assert "Invalid or expired" in str(exc_info.value.message)


# =============================================================================
# Property 8: Authorization verification
# Feature: registry-model-migration, Property 8: Authorization verification
# Validates: Requirements 3.3, 3.5
# =============================================================================


@pytest.mark.asyncio
class TestAuthorizationVerification:
    """Property 8: Authorization verification tests.

    For any registration request, the registry SHALL verify the authenticated
    caller is authorized to publish the specified package. Unauthorized requests
    SHALL be rejected with 403 status.
    """

    @given(
        package_name=st.builds(
            lambda base: f"{base}-{uuid.uuid4().hex[:8]}",
            st.from_regex(r"[a-z][a-z0-9]{2,10}", fullmatch=True),
        ),
        user_id=st.builds(lambda: f"user_{uuid.uuid4().hex[:16]}"),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_first_publisher_allowed(
        self,
        package_name: str,
        user_id: str,
        test_session: AsyncSession,
    ):
        """Property 8: First publisher is allowed to create new package.

        Feature: registry-model-migration, Property 8: Authorization verification
        Validates: Requirements 3.3, 3.5
        """
        user = AuthenticatedUser(
            user_id=user_id,
            auth_type="api_token",
            scopes=["upload"],
        )

        # Package doesn't exist - first publisher should be allowed
        result = await verify_package_ownership(test_session, package_name, user)
        assert result is None  # None means package doesn't exist, first publisher allowed

    @given(
        package_name=st.builds(
            lambda base: f"{base}-{uuid.uuid4().hex[:8]}",
            st.from_regex(r"[a-z][a-z0-9]{2,10}", fullmatch=True),
        ),
        owner_id=st.builds(lambda: f"user_{uuid.uuid4().hex[:16]}"),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_owner_allowed(
        self,
        package_name: str,
        owner_id: str,
        test_session: AsyncSession,
    ):
        """Property 8: Package owner is allowed to publish.

        Feature: registry-model-migration, Property 8: Authorization verification
        Validates: Requirements 3.3, 3.5
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package",
        )
        test_session.add(package)

        # Add owner as publisher
        publisher = Publisher(
            package_name=package_name,
            publisher_id=owner_id,
            publisher_type="api_token",
            is_owner=True,
        )
        test_session.add(publisher)
        await test_session.commit()

        user = AuthenticatedUser(
            user_id=owner_id,
            auth_type="api_token",
            scopes=["upload"],
        )

        # Owner should be allowed
        result = await verify_package_ownership(test_session, package_name, user)
        assert result is not None
        assert result.name == package_name

    @given(
        package_name=st.builds(
            lambda base: f"{base}-{uuid.uuid4().hex[:8]}",
            st.from_regex(r"[a-z][a-z0-9]{2,10}", fullmatch=True),
        ),
        owner_id=st.builds(lambda: f"user_{uuid.uuid4().hex[:16]}"),
        other_user_id=st.builds(lambda: f"user_{uuid.uuid4().hex[:16]}"),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_non_owner_rejected(
        self,
        package_name: str,
        owner_id: str,
        other_user_id: str,
        test_session: AsyncSession,
    ):
        """Property 8: Non-owner is rejected with ForbiddenError.

        Feature: registry-model-migration, Property 8: Authorization verification
        Validates: Requirements 3.3, 3.5
        """
        # Skip if user IDs happen to be the same
        if owner_id == other_user_id:
            return

        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package",
        )
        test_session.add(package)

        # Add owner as publisher
        publisher = Publisher(
            package_name=package_name,
            publisher_id=owner_id,
            publisher_type="api_token",
            is_owner=True,
        )
        test_session.add(publisher)
        await test_session.commit()

        # Different user tries to publish
        other_user = AuthenticatedUser(
            user_id=other_user_id,
            auth_type="api_token",
            scopes=["upload"],
        )

        with pytest.raises(ForbiddenError) as exc_info:
            await verify_package_ownership(test_session, package_name, other_user)

        assert "Not authorized" in str(exc_info.value.message)

    @given(
        package_name=st.builds(
            lambda base: f"{base}-{uuid.uuid4().hex[:8]}",
            st.from_regex(r"[a-z][a-z0-9]{2,10}", fullmatch=True),
        ),
        repo=st.builds(
            lambda: f"owner-{uuid.uuid4().hex[:6]}/repo-{uuid.uuid4().hex[:6]}",
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_trusted_publisher_allowed(
        self,
        package_name: str,
        repo: str,
        test_session: AsyncSession,
    ):
        """Property 8: Trusted publisher with matching repository is allowed.

        Feature: registry-model-migration, Property 8: Authorization verification
        Validates: Requirements 3.3, 3.5
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package",
        )
        test_session.add(package)

        # Add trusted publisher
        publisher = Publisher(
            package_name=package_name,
            publisher_id=f"github:{repo}",
            publisher_type="trusted_publisher",
            is_owner=True,
            github_repository=repo,
        )
        test_session.add(publisher)
        await test_session.commit()

        user = AuthenticatedUser(
            user_id=f"github:{repo}",
            auth_type="trusted_publisher",
            scopes=["upload"],
            github_repository=repo,
        )

        # Trusted publisher should be allowed
        result = await verify_package_ownership(test_session, package_name, user)
        assert result is not None
        assert result.name == package_name

    @given(
        package_name=st.builds(
            lambda base: f"{base}-{uuid.uuid4().hex[:8]}",
            st.from_regex(r"[a-z][a-z0-9]{2,10}", fullmatch=True),
        ),
        owner_repo=st.builds(
            lambda: f"owner-{uuid.uuid4().hex[:6]}/repo-{uuid.uuid4().hex[:6]}",
        ),
        other_repo=st.builds(
            lambda: f"owner-{uuid.uuid4().hex[:6]}/repo-{uuid.uuid4().hex[:6]}",
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_wrong_trusted_publisher_rejected(
        self,
        package_name: str,
        owner_repo: str,
        other_repo: str,
        test_session: AsyncSession,
    ):
        """Property 8: Trusted publisher with wrong repository is rejected.

        Feature: registry-model-migration, Property 8: Authorization verification
        Validates: Requirements 3.3, 3.5
        """
        # Skip if repos happen to be the same
        if owner_repo == other_repo:
            return

        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package",
        )
        test_session.add(package)

        # Add trusted publisher for owner_repo
        publisher = Publisher(
            package_name=package_name,
            publisher_id=f"github:{owner_repo}",
            publisher_type="trusted_publisher",
            is_owner=True,
            github_repository=owner_repo,
        )
        test_session.add(publisher)
        await test_session.commit()

        # Different repo tries to publish
        other_user = AuthenticatedUser(
            user_id=f"github:{other_repo}",
            auth_type="trusted_publisher",
            scopes=["upload"],
            github_repository=other_repo,
        )

        with pytest.raises(ForbiddenError) as exc_info:
            await verify_package_ownership(test_session, package_name, other_user)

        assert "Not authorized" in str(exc_info.value.message)


class TestRequireScope:
    """Tests for require_scope dependency."""

    @pytest.mark.asyncio
    async def test_missing_scope_raises_forbidden(self, app):
        """Property 8: Missing required scope raises ForbiddenError.

        Feature: registry-model-migration, Property 8: Authorization verification
        Validates: Requirements 3.3, 3.5
        """
        user = AuthenticatedUser(
            user_id="test_user",
            auth_type="api_token",
            scopes=["read"],  # Missing "upload" scope
        )

        # Create the scope checker
        check_scope = require_scope("upload")

        # Mock get_current_user to return our user
        with patch("island_api.auth.tokens.get_current_user", return_value=user):
            with pytest.raises(ForbiddenError) as exc_info:
                await check_scope(user)

            assert "Missing required scope" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_wildcard_scope_allowed(self, app):
        """Property 8: Wildcard scope allows any operation.

        Feature: registry-model-migration, Property 8: Authorization verification
        Validates: Requirements 3.3, 3.5
        """
        user = AuthenticatedUser(
            user_id="test_user",
            auth_type="api_token",
            scopes=["*"],  # Wildcard scope
        )

        # Create the scope checker
        check_scope = require_scope("upload")

        # Should not raise
        result = await check_scope(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_matching_scope_allowed(self, app):
        """Property 8: Matching scope allows operation.

        Feature: registry-model-migration, Property 8: Authorization verification
        Validates: Requirements 3.3, 3.5
        """
        user = AuthenticatedUser(
            user_id="test_user",
            auth_type="api_token",
            scopes=["upload"],
        )

        # Create the scope checker
        check_scope = require_scope("upload")

        # Should not raise
        result = await check_scope(user)
        assert result == user
