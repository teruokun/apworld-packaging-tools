# SPDX-License-Identifier: MIT
"""Property-based tests for CLI install command.

These tests validate:
- Property 4: Client-side checksum verification

Feature: registry-model-migration
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

# Import main first to avoid circular import issues
from island_cli.main import cli  # noqa: F401
from island_cli.commands.install import (
    ChecksumMismatchError,
    _compute_sha256,
    download_and_verify,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid SHA256 checksum: 64 lowercase hex characters
valid_sha256 = st.from_regex(r"[0-9a-f]{64}", fullmatch=True)

# File content for testing
file_content_strategy = st.binary(min_size=100, max_size=10000)


# =============================================================================
# Property 4: Client-side checksum verification
# Feature: registry-model-migration, Property 4: Client-side checksum verification
# Validates: Requirements 5.3, 5.4, 5.5
# =============================================================================


class TestClientChecksumVerification:
    """Property 4: Client-side checksum verification tests.

    For any package download, the client SHALL compute the SHA256 checksum
    of the downloaded content and verify it matches the registry-provided
    expected checksum. Mismatches SHALL cause the download to be rejected.
    """

    @given(content=file_content_strategy)
    @settings(max_examples=100)
    def test_compute_sha256_produces_valid_hash(self, content: bytes):
        """Property 4: SHA256 computation produces valid 64-char lowercase hex.

        Feature: registry-model-migration, Property 4: Client-side checksum verification
        Validates: Requirements 5.3
        """
        result = _compute_sha256(content)

        # Verify format
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

        # Verify correctness
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    @given(content=file_content_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_matching_checksum_accepted(self, content: bytes, tmp_path: Path):
        """Property 4: Matching checksums are accepted and file is written.

        Feature: registry-model-migration, Property 4: Client-side checksum verification
        Validates: Requirements 5.3, 5.4
        """
        # Compute actual checksum
        actual_sha256 = hashlib.sha256(content).hexdigest()
        output_path = tmp_path / f"test_{actual_sha256[:8]}.island"

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.content = content
        mock_response.raise_for_status = MagicMock()

        with patch("island_cli.commands.install.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Should not raise
            size = download_and_verify(
                url="https://example.com/test.island",
                expected_sha256=actual_sha256,
                output_path=output_path,
            )

            # Verify file was written correctly
            assert output_path.exists()
            assert output_path.read_bytes() == content
            assert size == len(content)

    @given(
        content=file_content_strategy,
        wrong_checksum=valid_sha256,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_mismatching_checksum_rejected(
        self, content: bytes, wrong_checksum: str, tmp_path: Path
    ):
        """Property 4: Mismatching checksums are rejected with ChecksumMismatchError.

        Feature: registry-model-migration, Property 4: Client-side checksum verification
        Validates: Requirements 5.4, 5.5
        """
        # Compute actual checksum
        actual_sha256 = hashlib.sha256(content).hexdigest()

        # Skip if by chance the random checksum matches
        if wrong_checksum.lower() == actual_sha256:
            return

        output_path = tmp_path / f"test_{wrong_checksum[:8]}.island"

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.content = content
        mock_response.raise_for_status = MagicMock()

        with patch("island_cli.commands.install.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ChecksumMismatchError) as exc_info:
                download_and_verify(
                    url="https://example.com/test.island",
                    expected_sha256=wrong_checksum,
                    output_path=output_path,
                )

            # Verify error contains expected and actual checksums
            error = exc_info.value
            assert error.expected == wrong_checksum.lower()
            assert error.actual == actual_sha256
            assert "Checksum verification failed" in str(error)

            # Verify file was NOT written
            assert not output_path.exists()

    @given(content=file_content_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_uppercase_checksum_normalized(self, content: bytes, tmp_path: Path):
        """Property 4: Uppercase checksums are normalized to lowercase for comparison.

        Feature: registry-model-migration, Property 4: Client-side checksum verification
        Validates: Requirements 5.3, 5.4
        """
        # Compute actual checksum and convert to uppercase
        actual_sha256 = hashlib.sha256(content).hexdigest()
        uppercase_sha256 = actual_sha256.upper()
        output_path = tmp_path / f"test_upper_{actual_sha256[:8]}.island"

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.content = content
        mock_response.raise_for_status = MagicMock()

        with patch("island_cli.commands.install.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Should not raise - uppercase should be normalized
            size = download_and_verify(
                url="https://example.com/test.island",
                expected_sha256=uppercase_sha256,
                output_path=output_path,
            )

            assert output_path.exists()
            assert size == len(content)

    @given(content=file_content_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_download_follows_redirects(self, content: bytes, tmp_path: Path):
        """Property 4: Downloads follow redirects to final URL.

        Feature: registry-model-migration, Property 4: Client-side checksum verification
        Validates: Requirements 5.2
        """
        actual_sha256 = hashlib.sha256(content).hexdigest()
        output_path = tmp_path / f"test_redirect_{actual_sha256[:8]}.island"

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.content = content
        mock_response.raise_for_status = MagicMock()

        with patch("island_cli.commands.install.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            download_and_verify(
                url="https://example.com/redirect",
                expected_sha256=actual_sha256,
                output_path=output_path,
            )

            # Verify client was created with follow_redirects=True
            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs.get("follow_redirects") is True

    def test_http_error_propagated(self, tmp_path: Path):
        """Property 4: HTTP errors are propagated to caller.

        Feature: registry-model-migration, Property 4: Client-side checksum verification
        Validates: Requirements 5.5
        """
        output_path = tmp_path / "test.island"

        with patch("island_cli.commands.install.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            with pytest.raises(httpx.ConnectError):
                download_and_verify(
                    url="https://example.com/test.island",
                    expected_sha256="a" * 64,
                    output_path=output_path,
                )

            # Verify file was NOT written
            assert not output_path.exists()

    def test_checksum_mismatch_error_message_is_descriptive(self):
        """Property 4: ChecksumMismatchError provides descriptive error message.

        Feature: registry-model-migration, Property 4: Client-side checksum verification
        Validates: Requirements 5.5
        """
        expected = "a" * 64
        actual = "b" * 64
        url = "https://example.com/test.island"

        error = ChecksumMismatchError(expected=expected, actual=actual, url=url)

        error_str = str(error)
        assert "Checksum verification failed" in error_str
        assert f"Expected: {expected}" in error_str
        assert f"Got: {actual}" in error_str
        assert f"URL: {url}" in error_str
        assert "tampered" in error_str or "corrupted" in error_str
