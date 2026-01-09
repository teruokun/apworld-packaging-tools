# SPDX-License-Identifier: MIT
"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APIConfig


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    # Startup: initialize database, storage, etc.
    config: APIConfig = app.state.config

    # Initialize database connection
    from .db import init_db

    await init_db(config.database)

    yield

    # Shutdown: cleanup resources
    from .db import close_db

    await close_db()


def create_app(config: APIConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: API configuration. If None, loads from environment.

    Returns:
        Configured FastAPI application instance.
    """
    if config is None:
        config = APIConfig.from_env()

    app = FastAPI(
        title=config.title,
        description=config.description,
        version=config.version,
        docs_url=config.docs_url,
        openapi_url=config.openapi_url,
        lifespan=lifespan,
    )

    # Store config in app state
    app.state.config = config

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add error handling middleware
    from .middleware.errors import add_error_handlers

    add_error_handlers(app)

    # Add rate limiting middleware if enabled
    if config.rate_limit.enabled:
        from .middleware.ratelimit import RateLimitMiddleware

        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=config.rate_limit.requests_per_minute,
            burst_size=config.rate_limit.burst_size,
        )

    # Register API routes
    from .routes import download, packages, upload

    app.include_router(packages.router, prefix=config.api_prefix, tags=["packages"])
    app.include_router(download.router, prefix=config.api_prefix, tags=["download"])
    app.include_router(upload.router, prefix=config.api_prefix, tags=["upload"])

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "version": config.version}

    return app


# Default app instance for uvicorn
app = create_app()
