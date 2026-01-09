# SPDX-License-Identifier: MIT
"""Pytest fixtures for API tests."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apworld_api import APIConfig, create_app
from apworld_api.db import get_session
from apworld_api.db.models import Author, Base, Keyword, Package, Version


@pytest.fixture
def test_config() -> APIConfig:
    """Create test configuration with in-memory SQLite."""
    config = APIConfig()
    config.database.url = "sqlite+aiosqlite:///:memory:"
    config.database.echo = False
    config.rate_limit.enabled = False
    config.storage.backend = "local"
    config.storage.local_path = "/tmp/test_packages"
    return config


@pytest_asyncio.fixture
async def test_engine(test_config: APIConfig):
    """Create test database engine."""
    engine = create_async_engine(
        test_config.database.url,
        echo=test_config.database.echo,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(test_config: APIConfig, test_engine):
    """Create test FastAPI application."""
    app = create_app(test_config)

    # Override database session dependency
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return app


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def sample_package(test_session: AsyncSession) -> Package:
    """Create a sample package for testing."""
    package = Package(
        name="pokemon-emerald",
        display_name="Pokemon Emerald",
        description="Pokemon Emerald randomizer for Archipelago",
        license="MIT",
        homepage="https://github.com/ArchipelagoMW/Archipelago",
        repository="https://github.com/ArchipelagoMW/Archipelago",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        total_downloads=100,
    )
    test_session.add(package)

    # Add authors
    author = Author(
        package_name="pokemon-emerald",
        name="Zunawe",
        email="zunawe@example.com",
    )
    test_session.add(author)

    # Add keywords
    for kw in ["pokemon", "gba", "emerald"]:
        keyword = Keyword(package_name="pokemon-emerald", keyword=kw)
        test_session.add(keyword)

    # Add version
    version = Version(
        package_name="pokemon-emerald",
        version="2.1.0",
        game="Pokemon Emerald",
        minimum_ap_version="0.5.0",
        maximum_ap_version="0.6.99",
        pure_python=True,
        published_at=datetime.now(timezone.utc),
        yanked=False,
    )
    test_session.add(version)

    await test_session.commit()
    await test_session.refresh(package)
    return package


@pytest_asyncio.fixture
async def sample_packages(test_session: AsyncSession) -> list[Package]:
    """Create multiple sample packages for testing."""
    packages = []

    for i, (name, display, game) in enumerate(
        [
            ("pokemon-emerald", "Pokemon Emerald", "Pokemon Emerald"),
            ("hollow-knight", "Hollow Knight", "Hollow Knight"),
            ("celeste", "Celeste", "Celeste"),
            ("stardew-valley", "Stardew Valley", "Stardew Valley"),
        ]
    ):
        package = Package(
            name=name,
            display_name=display,
            description=f"{display} randomizer for Archipelago",
            license="MIT",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            total_downloads=100 * (i + 1),
        )
        test_session.add(package)

        # Add version
        version = Version(
            package_name=name,
            version="1.0.0",
            game=game,
            pure_python=True,
            published_at=datetime.now(timezone.utc),
            yanked=False,
        )
        test_session.add(version)

        packages.append(package)

    await test_session.commit()
    return packages
