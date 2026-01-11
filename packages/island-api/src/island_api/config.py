# SPDX-License-Identifier: MIT
"""API server configuration."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    url: str = "sqlite:///./island_repository.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


@dataclass
class StorageConfig:
    """Package storage configuration.

    DEPRECATED: This configuration is no longer used in the registry-only model.
    The registry no longer stores package files - it only stores metadata and
    external URLs. Packages are hosted externally (e.g., on GitHub Releases).

    This class is kept for backward compatibility with existing deployments
    but has no effect on the registry's behavior.
    """

    backend: str = "local"  # "local" or "s3" - DEPRECATED
    local_path: str = "./packages"  # DEPRECATED
    s3_bucket: Optional[str] = None  # DEPRECATED
    s3_prefix: str = "packages/"  # DEPRECATED


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    enabled: bool = True
    requests_per_minute: int = 100
    burst_size: int = 20


@dataclass
class AuthConfig:
    """Authentication configuration."""

    require_auth_for_upload: bool = True
    api_token_header: str = "Authorization"
    oidc_enabled: bool = False
    oidc_issuer: Optional[str] = None
    oidc_audience: Optional[str] = None


@dataclass
class APIConfig:
    """Main API server configuration."""

    # Server settings
    title: str = "Island Package Index"
    description: str = (
        "Registry server for Island package metadata and discovery (registry-only model)"
    )
    version: str = "0.1.0"
    debug: bool = False

    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)

    # API settings
    api_prefix: str = "/v1/island"
    docs_url: str = "/docs"
    openapi_url: str = "/openapi.json"

    @classmethod
    def from_env(cls) -> "APIConfig":
        """Create configuration from environment variables."""
        import os

        config = cls()

        # Database
        if db_url := os.getenv("ISLAND_DATABASE_URL"):
            config.database.url = db_url
        config.database.echo = os.getenv("ISLAND_DATABASE_ECHO", "").lower() == "true"

        # Storage
        if storage_backend := os.getenv("ISLAND_STORAGE_BACKEND"):
            config.storage.backend = storage_backend
        if local_path := os.getenv("ISLAND_STORAGE_LOCAL_PATH"):
            config.storage.local_path = local_path
        if s3_bucket := os.getenv("ISLAND_STORAGE_S3_BUCKET"):
            config.storage.s3_bucket = s3_bucket

        # Rate limiting
        config.rate_limit.enabled = os.getenv("ISLAND_RATE_LIMIT_ENABLED", "true").lower() == "true"
        if rpm := os.getenv("ISLAND_RATE_LIMIT_RPM"):
            config.rate_limit.requests_per_minute = int(rpm)

        # Auth
        config.auth.oidc_enabled = os.getenv("ISLAND_OIDC_ENABLED", "").lower() == "true"
        if oidc_issuer := os.getenv("ISLAND_OIDC_ISSUER"):
            config.auth.oidc_issuer = oidc_issuer

        # Debug
        config.debug = os.getenv("ISLAND_DEBUG", "").lower() == "true"

        return config
