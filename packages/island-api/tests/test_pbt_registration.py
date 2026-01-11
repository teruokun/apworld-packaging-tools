# SPDX-License-Identifier: MIT
"""Property-based tests for package registration API.

These tests validate:
- Property 1: Registration URL verification
- Property 2: Registration checksum verification
- Property 3: Checksum format validation

Feature: registry-model-migration
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from pydantic import HttpUrl, ValidationError

from island_api.models.registration import (
    DistributionRegistration,
    PackageRegistration,
    validate_sha256_format,
)
from island_api.routes.register import (
    ChecksumMismatchError,
    SizeMismatchError,
    URLValidationError,
    download_and_verify_checksum,
    verify_url_accessible,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid SHA256 checksum: 64 lowercase hex characters
valid_sha256 = st.from_regex(r"[0-9a-f]{64}", fullmatch=True)

# Invalid SHA256 checksums
invalid_sha256_wrong_length = st.from_regex(r"[0-9a-f]{1,63}|[0-9a-f]{65,100}", fullmatch=True)
invalid_sha256_wrong_chars = st.from_regex(r"[0-9a-f]{0,63}[g-zG-Z][0-9a-f]{0,63}", fullmatch=True)
invalid_sha256_uppercase = st.from_regex(r"[0-9A-F]{64}", fullmatch=True).filter(
    lambda s: any(c.isupper() for c in s)
)

# Valid HTTPS URLs
valid_https_url = st.sampled_from(
    [
        "https://github.com/user/repo/releases/download/v1.0.0/package.island",
        "https://example.com/downloads/package-1.0.0.island",
        "https://cdn.example.org/packages/test-1.0.0-py3-none-any.island",
    ]
)

# Invalid HTTP URLs (not HTTPS)
invalid_http_url = st.sampled_from(
    [
        "http://example.com/package.island",
        "http://github.com/user/repo/releases/download/v1.0.0/package.island",
    ]
)

# Valid package names
valid_package_name = st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True)

# Valid version strings
valid_version = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)

# Valid platform tags
valid_platform_tag = st.sampled_from(
    [
        "py3-none-any",
        "cp311-cp311-win_amd64",
        "cp311-cp311-macosx_11_0_arm64",
        "cp312-cp312-linux_x86_64",
    ]
)

# File content for testing
file_content_strategy = st.binary(min_size=100, max_size=10000)


# =============================================================================
# Property 3: Checksum format validation
# Feature: registry-model-migration, Property 3: Checksum format validation
# Validates: Requirements 9.1, 9.2, 9.3
# =============================================================================


class TestChecksumFormatValidation:
    """Property 3: Checksum format validation tests.

    For any checksum provided in a registration request, the registry SHALL
    validate it is exactly 64 lowercase hexadecimal characters. Invalid
    formats SHALL be rejected.
    """

    @given(checksum=valid_sha256)
    @settings(max_examples=100)
    def test_valid_sha256_accepted(self, checksum: str):
        """Property 3: Valid SHA256 checksums (64 lowercase hex chars) are accepted.

        Feature: registry-model-migration, Property 3: Checksum format validation
        Validates: Requirements 9.1, 9.2, 9.3
        """
        result = validate_sha256_format(checksum)
        assert result == checksum.lower()
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    @given(checksum=invalid_sha256_wrong_length)
    @settings(max_examples=100)
    def test_wrong_length_rejected(self, checksum: str):
        """Property 3: Checksums with wrong length are rejected.

        Feature: registry-model-migration, Property 3: Checksum format validation
        Validates: Requirements 9.1, 9.2, 9.3
        """
        with pytest.raises(ValueError) as exc_info:
            validate_sha256_format(checksum)
        assert "64 characters" in str(exc_info.value) or "hexadecimal" in str(exc_info.value)

    @given(checksum=invalid_sha256_wrong_chars)
    @settings(max_examples=100)
    def test_invalid_chars_rejected(self, checksum: str):
        """Property 3: Checksums with invalid characters are rejected.

        Feature: registry-model-migration, Property 3: Checksum format validation
        Validates: Requirements 9.1, 9.2, 9.3
        """
        with pytest.raises(ValueError) as exc_info:
            validate_sha256_format(checksum)
        # Should fail on either length or character validation
        error_msg = str(exc_info.value)
        assert "64 characters" in error_msg or "hexadecimal" in error_msg

    @given(checksum=st.from_regex(r"[0-9A-Fa-f]{64}", fullmatch=True))
    @settings(max_examples=100)
    def test_uppercase_normalized_to_lowercase(self, checksum: str):
        """Property 3: Uppercase hex characters are normalized to lowercase.

        Feature: registry-model-migration, Property 3: Checksum format validation
        Validates: Requirements 9.2
        """
        result = validate_sha256_format(checksum)
        assert result == checksum.lower()
        assert all(c in "0123456789abcdef" for c in result)


class TestDistributionRegistrationValidation:
    """Tests for DistributionRegistration model validation."""

    @given(
        sha256=valid_sha256,
        size=st.integers(min_value=1, max_value=100000000),
        platform_tag=valid_platform_tag,
    )
    @settings(max_examples=50)
    def test_valid_distribution_registration(
        self,
        sha256: str,
        size: int,
        platform_tag: str,
    ):
        """Valid distribution registrations are accepted."""
        dist = DistributionRegistration(
            filename="test-package-1.0.0-py3-none-any.island",
            url="https://github.com/user/repo/releases/download/v1.0.0/test.island",
            sha256=sha256,
            size=size,
            platform_tag=platform_tag,
        )
        assert dist.sha256 == sha256.lower()
        assert dist.size == size
        assert dist.platform_tag == platform_tag

    @given(sha256=invalid_sha256_wrong_length)
    @settings(max_examples=50)
    def test_invalid_sha256_in_distribution_rejected(self, sha256: str):
        """Distribution registrations with invalid SHA256 are rejected."""
        with pytest.raises(ValidationError):
            DistributionRegistration(
                filename="test.island",
                url="https://example.com/test.island",
                sha256=sha256,
                size=1000,
                platform_tag="py3-none-any",
            )

    def test_http_url_rejected(self):
        """Distribution registrations with HTTP (not HTTPS) URLs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DistributionRegistration(
                filename="test.island",
                url="http://example.com/test.island",
                sha256="a" * 64,
                size=1000,
                platform_tag="py3-none-any",
            )
        assert "HTTPS" in str(exc_info.value)


# =============================================================================
# Property 1: Registration URL verification
# Feature: registry-model-migration, Property 1: Registration URL verification
# Validates: Requirements 2.4, 8.2
# =============================================================================


@pytest.mark.asyncio
class TestURLVerification:
    """Property 1: Registration URL verification tests.

    For any registration request with distribution URLs, the registry SHALL
    verify each URL is accessible (returns HTTP 2xx) before accepting the
    registration. If any URL is inaccessible, the registration SHALL be rejected.
    """

    @given(url=valid_https_url)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_accessible_url_accepted(self, url: str):
        """Property 1: Accessible HTTPS URLs are accepted.

        Feature: registry-model-migration, Property 1: Registration URL verification
        Validates: Requirements 2.4, 8.2
        """
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(return_value=mock_response)

        # Should not raise
        await verify_url_accessible(mock_client, HttpUrl(url))
        mock_client.head.assert_called_once()

    @given(url=valid_https_url)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_inaccessible_url_rejected(self, url: str):
        """Property 1: Inaccessible URLs are rejected with URLValidationError.

        Feature: registry-model-migration, Property 1: Registration URL verification
        Validates: Requirements 2.4, 8.2
        """
        # Mock HTTP error response
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(URLValidationError) as exc_info:
            await verify_url_accessible(mock_client, HttpUrl(url))

        assert "Could not connect" in str(exc_info.value.detail)

    @given(url=valid_https_url, status_code=st.sampled_from([400, 401, 403, 404, 500, 502, 503]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_non_2xx_status_rejected(self, url: str, status_code: int):
        """Property 1: Non-2xx HTTP status codes are rejected.

        Feature: registry-model-migration, Property 1: Registration URL verification
        Validates: Requirements 2.4, 8.2
        """
        # Mock HTTP error response
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(return_value=mock_response)

        with pytest.raises(URLValidationError) as exc_info:
            await verify_url_accessible(mock_client, HttpUrl(url))

        assert f"HTTP {status_code}" in str(exc_info.value.detail)

    async def test_timeout_rejected(self):
        """Property 1: Timeout errors are rejected with URLValidationError.

        Feature: registry-model-migration, Property 1: Registration URL verification
        Validates: Requirements 2.4, 8.2
        """
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.head = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        with pytest.raises(URLValidationError) as exc_info:
            await verify_url_accessible(
                mock_client,
                HttpUrl("https://example.com/test.island"),
            )

        assert "timed out" in str(exc_info.value.detail)


# =============================================================================
# Property 2: Registration checksum verification
# Feature: registry-model-migration, Property 2: Registration checksum verification
# Validates: Requirements 2.5, 2.6
# =============================================================================


@pytest.mark.asyncio
class TestChecksumVerification:
    """Property 2: Registration checksum verification tests.

    For any registration request, the registry SHALL download each asset and
    verify its SHA256 checksum matches the provided value. If any checksum
    mismatches, the registration SHALL be rejected with a descriptive error.
    """

    @given(content=file_content_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_matching_checksum_accepted(self, content: bytes):
        """Property 2: Matching checksums are accepted.

        Feature: registry-model-migration, Property 2: Registration checksum verification
        Validates: Requirements 2.5, 2.6
        """
        # Compute actual checksum
        actual_sha256 = hashlib.sha256(content).hexdigest()

        # Create distribution with correct checksum
        dist = DistributionRegistration(
            filename="test.island",
            url="https://example.com/test.island",
            sha256=actual_sha256,
            size=len(content),
            platform_tag="py3-none-any",
        )

        # Mock successful download
        mock_response = MagicMock()
        mock_response.content = content
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        # Should not raise
        await download_and_verify_checksum(mock_client, dist)

    @given(
        content=file_content_strategy,
        wrong_checksum=valid_sha256,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_mismatching_checksum_rejected(self, content: bytes, wrong_checksum: str):
        """Property 2: Mismatching checksums are rejected with ChecksumMismatchError.

        Feature: registry-model-migration, Property 2: Registration checksum verification
        Validates: Requirements 2.5, 2.6
        """
        # Compute actual checksum
        actual_sha256 = hashlib.sha256(content).hexdigest()

        # Skip if by chance the random checksum matches
        if wrong_checksum == actual_sha256:
            return

        # Create distribution with wrong checksum
        dist = DistributionRegistration(
            filename="test.island",
            url="https://example.com/test.island",
            sha256=wrong_checksum,
            size=len(content),
            platform_tag="py3-none-any",
        )

        # Mock download returning different content
        mock_response = MagicMock()
        mock_response.content = content
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(ChecksumMismatchError) as exc_info:
            await download_and_verify_checksum(mock_client, dist)

        assert "Checksum mismatch" in str(exc_info.value.detail)
        assert wrong_checksum in str(exc_info.value.detail)
        assert actual_sha256 in str(exc_info.value.detail)

    @given(
        content=file_content_strategy,
        size_diff=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_mismatching_size_rejected(self, content: bytes, size_diff: int):
        """Property 2: Mismatching file sizes are rejected with SizeMismatchError.

        Feature: registry-model-migration, Property 2: Registration checksum verification
        Validates: Requirements 2.5
        """
        actual_sha256 = hashlib.sha256(content).hexdigest()
        actual_size = len(content)
        wrong_size = actual_size + size_diff

        # Create distribution with wrong size
        dist = DistributionRegistration(
            filename="test.island",
            url="https://example.com/test.island",
            sha256=actual_sha256,
            size=wrong_size,
            platform_tag="py3-none-any",
        )

        # Mock download
        mock_response = MagicMock()
        mock_response.content = content
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(SizeMismatchError) as exc_info:
            await download_and_verify_checksum(mock_client, dist)

        assert "Size mismatch" in str(exc_info.value.detail)
        assert str(wrong_size) in str(exc_info.value.detail)
        assert str(actual_size) in str(exc_info.value.detail)

    @given(content=file_content_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_download_failure_rejected(self, content: bytes):
        """Property 2: Download failures are rejected with URLValidationError.

        Feature: registry-model-migration, Property 2: Registration checksum verification
        Validates: Requirements 2.5, 2.6
        """
        actual_sha256 = hashlib.sha256(content).hexdigest()

        dist = DistributionRegistration(
            filename="test.island",
            url="https://example.com/test.island",
            sha256=actual_sha256,
            size=len(content),
            platform_tag="py3-none-any",
        )

        # Mock download failure
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(URLValidationError) as exc_info:
            await download_and_verify_checksum(mock_client, dist)

        assert "Could not connect" in str(exc_info.value.detail)
