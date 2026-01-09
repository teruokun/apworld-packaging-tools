# SPDX-License-Identifier: MIT
"""API server configuration."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    url: str = "sqlite:///./apworld_repository.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


@dataclass
class StorageConfig:
    """Package storage configuration."""

    backend: str = "local"  # "local" or "s3"
    local_path: str = "./packages"
    s3_bucket: Optional[str] = None
    s3_prefix: str = "packages/"


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
    title: str = "APWorld Package Index"
    description: str = "Repository server for APWorld package hosting and discovery"
    version: str = "0.1.0"
    debug: bool = False

    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)

    # API settings
    api_prefix: str = "/v1"
    docs_url: str = "/docs"
    openapi_url: str = "/openapi.json"

    @classmethod
    def from_env(cls) -> "APIConfig":
        """Create configuration from environment variables."""
        import os

        config = cls()

        # Database
        if db_url := os.getenv("APWORLD_DATABASE_URL"):
            config.database.url = db_url
        config.database.echo = os.getenv("APWORLD_DATABASE_ECHO", "").lower() == "true"

        # Storage
        if storage_backend := os.getenv("APWORLD_STORAGE_BACKEND"):
            config.storage.backend = storage_backend
        if local_path := os.getenv("APWORLD_STORAGE_LOCAL_PATH"):
            config.storage.local_path = local_path
        if s3_bucket := os.getenv("APWORLD_STORAGE_S3_BUCKET"):
            config.storage.s3_bucket = s3_bucket

        # Rate limiting
        config.rate_limit.enabled = (
            os.getenv("APWORLD_RATE_LIMIT_ENABLED", "true").lower() == "true"
        )
        if rpm := os.getenv("APWORLD_RATE_LIMIT_RPM"):
            config.rate_limit.requests_per_minute = int(rpm)

        # Auth
        config.auth.oidc_enabled = os.getenv("APWORLD_OIDC_ENABLED", "").lower() == "true"
        if oidc_issuer := os.getenv("APWORLD_OIDC_ISSUER"):
            config.auth.oidc_issuer = oidc_issuer

        # Debug
        config.debug = os.getenv("APWORLD_DEBUG", "").lower() == "true"

        return config
