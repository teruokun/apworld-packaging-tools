# SPDX-License-Identifier: MIT
"""Repository server for APWorld package hosting and discovery."""

__version__ = "0.1.0"

from .app import create_app
from .checksum import (
    ChecksumMismatchError,
    compute_sha256,
    compute_sha256_file,
    compute_sha256_stream,
    verify_checksum,
    verify_checksum_file,
)
from .config import APIConfig, AuthConfig, DatabaseConfig, RateLimitConfig, StorageConfig
from .middleware.errors import (
    APIError,
    ErrorCode,
    ForbiddenError,
    InvalidManifestError,
    InvalidVersionError,
    PackageNotFoundError,
    RateLimitedError,
    UnauthorizedError,
    VersionExistsError,
    VersionNotFoundError,
)

__all__ = [
    # App factory
    "create_app",
    # Configuration
    "APIConfig",
    "AuthConfig",
    "DatabaseConfig",
    "RateLimitConfig",
    "StorageConfig",
    # Checksum utilities
    "ChecksumMismatchError",
    "compute_sha256",
    "compute_sha256_file",
    "compute_sha256_stream",
    "verify_checksum",
    "verify_checksum_file",
    # Errors
    "APIError",
    "ErrorCode",
    "ForbiddenError",
    "InvalidManifestError",
    "InvalidVersionError",
    "PackageNotFoundError",
    "RateLimitedError",
    "UnauthorizedError",
    "VersionExistsError",
    "VersionNotFoundError",
]
